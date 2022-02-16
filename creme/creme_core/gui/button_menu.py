# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2022  Hybird
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

from __future__ import annotations

import logging
from typing import (
    Dict,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from django.template.loader import get_template

from ..models import CremeEntity

logger = logging.getLogger(__name__)


class Button:
    # ID of the button, stored in DB (ie: the button configuration), to retrieve
    # the right button class (so it must be unique)
    # Override it in child class with a value generated by 'generate_id()'.
    id_: str = ''

    # Label used in the configuration GUI to display the button (see models.ButtonMenuItem)
    # Tips: use gettext_lazy()
    verbose_name: str = 'BUTTON'

    # Description used as tool-tips
    # Tips: use gettext_lazy()
    description: str = ''

    # Name/path of the template used to render the button.
    template_name: str = 'creme_core/buttons/place-holder.html'

    # permission: Optional[str] = None
    # Permission string(s) ; an empty value means no permission is needed.
    #  eg: 'myapp.add_mymodel'
    # BEWARE: you have to use the template context variable "has_perm"
    #         (computed from 'permissions' -- see 'has_perm()' ) yourself !!
    permissions: Union[str, Sequence[str]] = ''

    def __eq__(self, other):
        return other.id_ == self.id_

    @staticmethod
    def generate_id(app_name: str, name: str) -> str:
        return f'button_{app_name}-{name}'

    def get_ctypes(self) -> Sequence[Type[CremeEntity]]:
        """
        @return A sequence of CremeEntity class that can have this type of button.
                Void sequence means that all types are ok.
                eg: (Contact, Organisation)
        """
        return ()

    def has_perm(self, context) -> bool:
        permissions = self.permissions
        if not permissions:
            return False

        return (
            context['user'].has_perm(permissions)
            if isinstance(permissions, str) else
            context['user'].has_perms(permissions)
        )

    def ok_4_display(self, entity: CremeEntity) -> bool:
        """Can this button be displayed on this entity's detail-view ?
        @param entity: CremeEntity which detail-view is displayed.
        @return True if the button can be displayed for 'entity'.
        """
        return True

    def render(self, context) -> str:
        context['has_perm'] = self.has_perm(context)
        context['description'] = self.description

        return get_template(self.template_name).render(context)


class ButtonsRegistry:
    class RegistrationError(Exception):
        pass

    def __init__(self):
        self._button_classes: Dict[str, Type[Button]] = {}

    def register(self, *button_classes: Type[Button]) -> ButtonsRegistry:
        """
        @type button_classes: creme_core.gui.menu_buttons.Button child classes.
        """
        setdefault = self._button_classes.setdefault

        for button_cls in button_classes:
            button_id = button_cls.id_

            if not button_id:
                raise self.RegistrationError(
                    f'Button class with empty id_: {button_cls}'
                )

            # if hasattr(button_cls, 'permission'):
            #     raise self.RegistrationError(
            #         f'Button class with old attribute "permission" '
            #         f'(use "permissions" instead): {button_cls}',
            #     )

            if setdefault(button_id, button_cls) is not button_cls:
                raise self.RegistrationError(
                    f"Duplicated button's ID (or button registered twice) : {button_id}"
                )

        return self

    def get_button(self, button_id: str) -> Optional[Button]:
        cls = self._button_classes.get(button_id)

        return cls() if cls else None

    def get_buttons(self, id_list: Iterable[str], entity: CremeEntity) -> Iterator[Button]:
        """Generate the Buttons to be displayed on the detail-view of an entity.
        Deprecated buttons & buttons that should not be displayed for this entity
        are ignored.
        @param id_list: Sequence of button IDs.
        @param entity: CremeEntity instance.
        @yield creme_core.gui.button_menu.Button instances.
        """
        button_classes = self._button_classes

        for button_id in id_list:
            button_cls = button_classes.get(button_id)

            if button_cls is None:
                logger.warning('Button seems deprecated: %s', button_id)
            else:
                button = button_cls()

                if button.ok_4_display(entity):
                    yield button

    def __iter__(self) -> Iterator[Tuple[str, Button]]:
        for b_id, b_cls in self._button_classes.items():
            yield b_id, b_cls()


button_registry = ButtonsRegistry()
