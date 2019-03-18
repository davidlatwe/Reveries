
import os
import pyblish.api
import reveries.utils

from avalon.vendor import clique
from reveries.plugins import DelegatablePackageExtractor, skip_stage
from reveries.maya import utils


class ExtractRender(DelegatablePackageExtractor):
    """Start GUI rendering if not delegate to Deadline
    """

    label = "Extract Render"
    order = pyblish.api.ExtractorOrder
    hosts = ["maya"]

    families = [
        "reveries.imgseq.render",
    ]

    representations = [
        "imageSequence",
        "imageSequenceSet",
    ]

    @skip_stage
    def extract_imageSequence(self):
        """Extract per renderlayer that has no AOVs
        """
        if not self.context.data.get("contractorAccepted"):
            self.start_local_rendering()

        repr_dir = self.create_package()

        # Assume the rendering has been completed at this time being,
        # start to check and extract the rendering outputs
        aov_name, aov_path = next(iter(self.data["outputPaths"].items()))

        self.add_sequence(aov_path, aov_name, repr_dir)

    @skip_stage
    def extract_imageSequenceSet(self):
        """Extract per renderlayer that has AOVs
        """
        if not self.context.data.get("contractorAccepted"):
            self.start_local_rendering()

        repr_dir = self.create_package()

        # Assume the rendering has been completed at this time being,
        # start to check and extract the rendering outputs
        for aov_name, aov_path in self.data["outputPaths"].items():
            self.add_sequence(aov_path, aov_name, repr_dir)

    def add_sequence(self, aov_path, aov_name, repr_dir):
        """
        """
        from maya import cmds

        seq_dir, pattern = os.path.split(aov_path)

        self.log.info("Collecting sequence from: %s" % seq_dir)
        assert os.path.isdir(seq_dir), "Sequence dir not exists."

        # (NOTE) Did not consider frame step (byFrame)
        start_frame = self.data["startFrame"]
        end_frame = self.data["endFrame"]

        collections, _ = clique.assemble(os.listdir(seq_dir),
                                         patterns=[clique.PATTERNS["frames"]])

        assert len(collections), "Extraction failed, no sequence found."

        for sequence in collections:
            if pattern == (sequence.head +
                           "#" * sequence.padding +
                           sequence.tail):
                break
        else:
            raise Exception("No sequence match this pattern: %s" % pattern)

        entry_fname = (sequence.head +
                       "%%0%dd" % sequence.padding +
                       sequence.tail)

        project = self.context.data["projectDoc"]
        width, height = reveries.utils.get_resolution_data(project)
        e_in, e_out, handles, _ = reveries.utils.get_timeline_data(project)
        camera = self.data["renderCam"][0]

        self.add_data({"sequence": {
            aov_name: {
                "imageFormat": self.data["fileExt"],
                "entryFileName": entry_fname,
                "seqStart": list(sequence.indexes)[0],
                "seqEnd": list(sequence.indexes)[-1],
                "startFrame": start_frame,
                "endFrame": end_frame,
                "byFrameStep": self.data["byFrameStep"],
                "edit_in": e_in,
                "edit_out": e_out,
                "handles": handles,
                "focalLength": cmds.getAttr(camera + ".focalLength"),
                "resolution": (width, height),
                "fps": self.context.data["fps"],
                "cameraUUID": utils.get_id(camera),
                "renderlayer": self.data["renderlayer"],
            }
        }})

        for file in [entry_fname % i for i in sequence.indexes]:
            src = seq_dir + "/" + file
            dst = os.path.join(repr_dir, aov_name, file)
            self.add_hardlink(src, dst)

    def start_local_rendering(self):
        """Start rendering at local with GUI
        """
        # reveries.maya.io.gui_rendering()
        raise NotImplementedError
