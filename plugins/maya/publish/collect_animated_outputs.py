
import pyblish.api


class CollectAnimatedOutputs(pyblish.api.InstancePlugin):
    """Collect transform animated nodes

    This only collect and extract animated transform nodes,
    shape node will not be included.

    """

    order = pyblish.api.CollectorOrder + 0.2
    label = "Collect Animated Outputs"
    hosts = ["maya"]
    families = [
        "reveries.animation",
    ]

    def process(self, instance):
        import maya.cmds as cmds
        from reveries.maya import lib, pipeline

        variant = instance.data["subset"][len("animation"):].lower()
        members = instance[:]

        # Re-Create instances
        context = instance.context
        context.remove(instance)
        source_data = instance.data

        ANIM_SET = "ControlSet"
        out_cache = dict()

        if variant == "default":
            # Collect animatable nodes from ControlSet of loaded subset
            out_sets = list()

            for node in cmds.ls(members, type="transform"):
                try:
                    # Must be containerized subset group node
                    pipeline.get_container_from_group(node)
                except AssertionError:
                    continue

                namespace = lib.get_ns(node)
                out_sets += cmds.ls("%s:*%s" % (namespace, ANIM_SET),
                                    sets=True)

            for node in out_sets:
                name = node.rsplit(":", 1)[-1][:-len(ANIM_SET)] or "Default"
                namespace = lib.get_ns(node)
                animatables = cmds.ls(cmds.sets(node, query=True),
                                      type="transform")

                key = (namespace, name)
                self.log.info("%s, %s" % key)
                if not animatables:
                    self.log.warning("No animatable (e.g. controllers) been "
                                     "found in '%s', skipping.." % node)
                    continue

                out_cache[key] = animatables

        else:
            # Collect animatable nodes from instance member
            for node in cmds.ls(members, type="transform"):
                namespace = lib.get_ns(node)
                try:
                    # Must be containerized
                    pipeline.get_container_from_namespace(namespace)
                except RuntimeError:
                    continue

                key = (namespace, variant)

                if key not in out_cache:
                    self.log.info("%s, %s" % key)
                    out_cache[key] = list()

                out_cache[key].append(node)

        for (namespace, name), animatables in sorted(out_cache.items()):
            container = pipeline.get_container_from_namespace(namespace)
            asset_id = cmds.getAttr(container + ".assetId")

            fixed_namespace = namespace[1:]  # Remove root ":"
            # For filesystem, remove other ":" if the namespace is nested
            fixed_namespace = fixed_namespace.replace(":", "._.")

            subset = ".".join(["animation",
                               fixed_namespace,
                               name])

            instance = context.create_instance(subset)
            instance.data.update(source_data)
            instance.data["subset"] = subset
            instance[:] = animatables
            instance.data["outAnim"] = animatables
            instance.data["animatedNamespace"] = namespace
            instance.data["animatedAssetId"] = asset_id
            # (NOTE) Although we put those animatable nodes to validate
            #        AvalonUUID existence, but currently AvalonUUID is
            #        not needed on load.
            instance.data["requireAvalonUUID"] = animatables
