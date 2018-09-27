
from maya import cmds
import avalon.maya
import avalon.io


class AnimationCreator(avalon.maya.Creator):
    """Any character or prop animation"""

    name = "animationDefault"
    label = "Animation"
    family = "reveries.animation"
    icon = "male"

    contractor = "deadline.maya.script"

    def process(self):
        project = avalon.io.find_one({"type": "project"},
                                     projection={"data": True})
        settings = project["data"]["pipeline"]["maya"]
        cache_mode = settings.get("animation_cache", "Alembic")
        self.data["format"] = cache_mode

        self.data["publish_contractor"] = self.contractor
        self.data["use_contractor"] = False

        instance = super(AnimationCreator, self).process()
        cmds.setAttr(instance + ".format", lock=True)
        cmds.setAttr(instance + ".publish_contractor", lock=True)

        return instance
