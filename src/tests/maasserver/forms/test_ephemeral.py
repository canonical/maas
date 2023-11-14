from maasserver.forms.ephemeral import ReleaseForm
from metadataserver.enum import SCRIPT_TYPE


class TestReleaseForm:
    def test_clean(self, factory):
        node = factory.make_Node()
        user = factory.make_User()
        form = ReleaseForm(node, user)
        assert form.is_valid()
        assert form.cleaned_data == {
            "comment": "",
            "erase": False,
            "secure_erase": False,
            "quick_erase": False,
            "force": False,
            "scripts": [],
        }

    def test_clean_erase(self, factory):
        node = factory.make_Node()
        user = factory.make_User()
        form = ReleaseForm(node, user, data={"erase": "true"})
        assert form.is_valid()
        assert form.cleaned_data == {
            "comment": "",
            "erase": True,
            "secure_erase": False,
            "quick_erase": False,
            "force": False,
            "scripts": ["wipe-disks"],
        }

    def test_clean_erase_flags(self, factory):
        node = factory.make_Node()
        user = factory.make_User()
        form = ReleaseForm(
            node, user, data={"quick_erase": "true", "secure_erase": "true"}
        )
        assert form.is_valid()
        assert form.cleaned_data == {
            "comment": "",
            "erase": False,
            "secure_erase": True,
            "quick_erase": True,
            "force": False,
            "scripts": ["wipe-disks"],
            "wipe-disks_secure_erase": True,
            "wipe-disks_quick_erase": True,
        }

    def test_clean_extra_scripts(self, factory):
        node = factory.make_Node()
        user = factory.make_User()
        script1 = factory.make_Script(script_type=SCRIPT_TYPE.RELEASE)
        script2 = factory.make_Script(script_type=SCRIPT_TYPE.RELEASE)
        form = ReleaseForm(
            node,
            user,
            data={"erase": "true", "scripts": [script1.name, script2.name]},
        )
        assert form.is_valid()
        assert form.cleaned_data["scripts"] == [
            script1.name,
            script2.name,
            "wipe-disks",
        ]
