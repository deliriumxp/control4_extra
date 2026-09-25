# Vendored from PyPI package pyControl4 2.0.2 (Apache-2.0, see LICENSE in this
# directory), unmodified except for two absolute self-imports changed to
# relative ones so this works as a bundled sub-package instead of a top-level
# pip-installed one.
#
# Why vendored instead of a normal pip requirement: the official
# home-assistant/core 'control4' integration pins an exact pyControl4 (1.5.0 then).$
# Only one version of a same-named top-level package can be installed in a
# Home Assistant Python environment at a time, so a plain 'pyControl4==2.0.2'
# requirement here would fight with the official integration for whichever
# version last got installed - flip-flopping across restarts. Vendoring under
# our own package name (control4_extra.vendor.pycontrol4) sidesteps that
# entirely: both integrations can run their own version at once.
from __future__ import annotations

from .director import C4Director


class C4Entity:
    def __init__(self, director: C4Director, item_id: int):
        """Creates a Control4 object.

        Parameters:
            `director` - A `pyControl4.director.C4Director` object that corresponds
                to the Control4 Director that the device is connected to.

            `item_id` - The Control4 item ID.
        """
        self.director = director
        self.item_id = int(item_id)
