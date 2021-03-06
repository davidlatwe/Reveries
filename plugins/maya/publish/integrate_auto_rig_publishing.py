
import pyblish.api


class IntegrateAutoRigPublishing(pyblish.api.InstancePlugin):
    """Auto publishing rig when model being published"""

    label = "Integrate Auto Rig Publishing"
    # This plugin must runs after disk and database integration
    order = pyblish.api.IntegratorOrder + 0.499

    hosts = ["maya"]
    families = ["reveries.model"]

    def process(self, instance):
        import os
        import re
        import sys
        import json
        import subprocess

        from avalon import io

        asset_doc = instance.data["assetDoc"]
        asset_name = asset_doc["name"]

        # Check asset's rigging task option
        value_path = "taskOptions.rigging.autoModelUpdate.value"
        value = asset_doc["data"]
        for entry in value_path.split("."):
            value = value.get(entry, {})
        if not value:
            # Auto model update not enabled
            return

        # Get subset, version documents from instance which just been
        # integrated.
        model_subset, model_version, _ = instance.data["toDatabase"]

        if model_version["name"] == 1:
            # First version of model, must not have dependent rig.
            return

        # Find all previous versions of model, only document id is needed.
        previous = io.find({"type": "version",
                            "parent": model_subset["_id"]},
                           sort=[("name", -1)],
                           projection={"_id": True},
                           skip=1)  # Skip the latest
        previous = set([str(p["_id"]) for p in previous])
        if not previous:
            self.log.warning("Model is now on version %d but has no previous, "
                             "skip updating rig." % model_version["name"])
            return

        # Any latest version of rig may not be using the latest model, so
        # we iterate through all rig subsets' latest version and compare
        # the dependency data with all previous model versions to find the
        # dependent.
        dependent_rigs = dict()

        for rig_subset in io.find({"type": "subset",
                                   "parent": asset_doc["_id"],
                                   "name": re.compile("rig*")},
                                  projection={"_id": True, "name": True}):

            latest_rig = io.find_one({"type": "version",
                                      "parent": rig_subset["_id"]},
                                     sort=[("name", -1)],
                                     projection={"data.dependencies": True})
            if latest_rig is None:
                # Not likely to happen, but just in case
                continue

            # Consider dependent if any dependency matched in model versions
            dependencies = set(latest_rig["data"]["dependencies"].keys())
            if dependencies.intersection(previous):
                dependent_rigs[str(latest_rig["_id"])] = rig_subset["name"]

        if not dependent_rigs:
            self.log.info("No rig to update, skip auto process.")
            return

        # Submit subprocess
        mayapy_exe = os.path.join(os.path.dirname(sys.executable),
                                  "mayapy.exe")
        cmd = [
            mayapy_exe,
            __file__,
            "asset_name={}".format(str(asset_name)),
            "model_subset={}".format(str(model_subset["name"])),
            "rig_versions={}".format(json.dumps(dependent_rigs)),
        ]

        print("auto rig cmd: {}".format(cmd))
        try:
            out_bytes = subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError:
            # Mark failed for future debug.
            io.update_many({"_id": model_version["_id"]},
                           {"$set": {"data.rigAutoUpdateFailed": True}})
            raise Exception("Model publish success but Rig auto update "
                            "failed. Please inform rigger or TD.")
        else:
            print(out_bytes)


class LauncherAutoPublish(object):

    def __init__(self):
        import sys
        import json

        kwargs = {}
        for _arg in sys.argv[1:]:
            _args_data = _arg.split("=")
            kwargs[_args_data[0]] = _args_data[1]

        self.asset_name = kwargs.get("asset_name", "")
        self.model_subset = kwargs.get("model_subset", "")
        self.rig_versions = json.loads(kwargs.get("rig_versions", "{}"))
        self.contexts = list()

    def run(self):
        from avalon import api, io
        import maya.standalone as standalone
        import pyblish.util

        standalone.initialize(name="python")

        # Get project root path and rig source files.
        jobs = dict()
        root = api.registered_root()
        for rig_version, rig_subset in self.rig_versions.items():
            version_id = io.ObjectId(rig_version)
            latest_ver = io.find_one({"type": "version", "_id": version_id})
            rig_source = latest_ver["data"]["source"].format(root=root)
            rig_source = rig_source.replace("\\", "/")
            if rig_source not in jobs:
                jobs[rig_source] = list()
            # One source scene may contains multiple rig subsets.
            jobs[rig_source].append(rig_subset)

        # Run publish process, till extraction
        for source, rig_subsets in jobs.items():
            self._publish(source, rig_subsets)

        # Run final integration only if all extraction succeed
        for context in self.contexts:
            context.data["_autoPublishingSkipUnlock"] = True
            pyblish.util.integrate(context=context)

        standalone.uninitialize()
        # Bye

    def _publish(self, rig_source, rig_subsets):
        import os
        import re
        import pyblish.util
        import maya.cmds as cmds
        from avalon import api
        from reveries.maya import lib

        # Switch task
        api.update_current_task(task="rigging", asset=self.asset_name)

        # Open rig source file
        cmds.file(rig_source, open=True, force=True)

        # Update all loaded model which subset name has matched
        _updated = False
        host = api.registered_host()
        for _container in host.ls():
            if _container["name"] == self.model_subset:
                api.update(_container)
                _updated = True

        if not _updated:
            # Not likely to happen, but just in case
            raise Exception("No matched model subset, this is a bug.")

        # Config rig instances' activities
        #   Activate rig instances that need to be published, and deactivate
        #   the rest.
        for instance_set in lib.lsAttr("id", "pyblish.avalon.instance"):
            active = cmds.getAttr(instance_set + ".subset") in rig_subsets
            cmds.setAttr(instance_set + ".active", active)

        # Save as file
        _tmp_dir = os.path.join(os.path.dirname(rig_source), "_auto_update")
        if not os.path.exists(_tmp_dir):
            os.mkdir(_tmp_dir)
            os.chmod(_tmp_dir, 777)
        # Compose a good file name
        basename, ext = os.path.splitext(os.path.basename(rig_source))
        if "auto_model_update" not in basename:
            _new_fname = "{}.auto_model_update.001{}".format(basename, ext)
        else:
            current_v = re.findall(".auto_model_update.(\\d+).", rig_source)[0]
            new_v = "{:03d}".format(int(current_v) + 1)
            _new_fname = "{}{}".format(basename, ext)
            _new_fname = _new_fname.replace(".{}.published.".format(current_v),
                                            ".{}.".format(new_v))

        _save_to = os.path.join(_tmp_dir, _new_fname)
        cmds.file(rename=_save_to)
        cmds.file(force=True, save=True)
        print("Saved to : {}".format(_save_to))

        # Publish
        pyblish.api.register_target("localhost")

        # Fix AvalonUUID before validate
        ValidateAvalonUUID = next(p for p in pyblish.api.discover()
                                  if p.__name__ == "ValidateAvalonUUID")
        for instance in pyblish.util.collect():
            try:
                ValidateAvalonUUID.fix_invalid_missing(instance)
            except Exception as e:
                print("Fix uuid failed: {}.".format(e))

        context = pyblish.util.collect()
        context.data["comment"] = "Auto update model to latest version."
        context = pyblish.util.validate(context=context)
        context = pyblish.util.extract(context=context)

        if not all(result["success"] for result in context.data["results"]):
            raise RuntimeError("Atomicity not held, aborting.")

        # Will run integration later..
        self.contexts.append(context)


if __name__ == "__main__":
    auto_publish = LauncherAutoPublish()
    auto_publish.run()

