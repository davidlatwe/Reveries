
import os
import pyblish.api

from reveries.plugins import PackageExtractor, skip_stage


class ExtractAtomsCrowdCache(PackageExtractor):

    label = "Extract AtomsCrowd Cache"
    order = pyblish.api.ExtractorOrder
    hosts = ["maya"]
    families = ["reveries.atomscrowd"]

    representations = [
        "atoms",
    ]

    @skip_stage
    def extract_atoms(self):
        from AtomsMaya.hostbridge.commands import MayaCommandsHostBridge

        start_frame = int(self.context.data.get("startFrame"))
        end_frame = int(self.context.data.get("endFrame"))

        package_path = self.create_package()

        entry_file = self.file_name("atoms")
        entry_path = os.path.join(package_path, entry_file)

        cache_dir = str(os.path.dirname(entry_path))
        cache_name = str(os.path.basename(entry_path).replace(".atoms", ""))

        agent_groups = self.data["AtomsAgentGroups"]
        MayaCommandsHostBridge.export_atoms_cache(cache_dir,
                                                  cache_name,
                                                  start_frame,
                                                  end_frame,
                                                  agent_groups)

        variation_file = self.file_name("json")
        variation_path = os.path.join(package_path, variation_file)

        with open(variation_path, "w") as variation:
            variation.write(self.data["variationStr"])

        self.add_data({
            "entryFileName": entry_file,
            "variationFile": variation_file,
            "startFrame": start_frame,
            "endFrame": end_frame,
        })
