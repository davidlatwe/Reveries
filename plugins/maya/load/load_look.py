
from reveries.maya.plugins import ReferenceLoader


class LookLoader(ReferenceLoader):
    """Specific loader for lookdev"""

    label = "Reference look"
    order = -10
    icon = "code-fork"
    color = "orange"

    families = ["reveries.look"]

    representations = [
        "mayaAscii",
    ]

    def process_reference(self, context, name, namespace, data):
        import os
        import json

        from maya import cmds
        from reveries.maya import lib

        entry_path = self.file_path(data["entry_fname"])

        try:
            existing_reference = cmds.file(entry_path,
                                           query=True,
                                           referenceNode=True)
        except RuntimeError as e:
            if e.message.rstrip() != "Cannot find the scene file.":
                raise

            self.log.info("Loading lookdev for the first time..")
            nodes = cmds.file(
                entry_path,
                namespace=namespace,
                reference=True,
                returnNewNodes=True
            )
        else:
            self.log.info("Reusing existing lookdev..")
            nodes = cmds.referenceQuery(existing_reference, nodes=True)
            namespace = nodes[0].split(":", 1)[0]

        # Assign shaders
        #
        relationship = self.file_path(data["link_fname"])

        # Expand $AVALON_PROJECT and friends, if used
        relationship = os.path.expandvars(relationship)

        if not os.path.isfile(relationship):
            self.log.warning("Look development asset "
                             "has no relationship data.\n"
                             "%s was not found" % self.fname)
            return nodes

        with open(relationship) as f:
            relationships = json.load(f)

        lib.apply_shaders(relationships, namespace)

        self[:] = nodes
