# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2010  Hybird
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

from creme_core.management.commands.creme_populate import BasePopulator
from creme_core.utils import create_or_update_models_instance as create

from creme_config.constants import MAPI_DOMAIN, MAPI_SERVER_SSL, MAPI_SERVER_URL
from creme_config.models.config_models import CremeKVConfig

class Populator(BasePopulator):
    def populate(self, *args, **kwargs):
        create(CremeKVConfig, id=MAPI_SERVER_URL, value="")
        create(CremeKVConfig, id=MAPI_DOMAIN,     value="")
        create(CremeKVConfig, id=MAPI_SERVER_SSL, value="0")
