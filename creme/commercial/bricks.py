# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2017  Hybird
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

from collections import defaultdict
from itertools import chain

from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from creme.creme_core.gui.bricks import Brick, PaginatedBrick, QuerysetBrick, list4url
from creme.creme_core.models import Relation, SettingValue

from creme.persons import get_organisation_model

from creme.opportunities import get_opportunity_model
from creme.opportunities.constants import REL_SUB_TARGETS

from creme import commercial
from .models import (CommercialApproach, MarketSegment, MarketSegmentDescription,
        CommercialAsset, MarketSegmentCharm, ActObjective, ActObjectivePatternComponent)
from .constants import DISPLAY_ONLY_ORGA_COM_APPROACH_ON_ORGA_DETAILVIEW, REL_OBJ_COMPLETE_GOAL


get_ct = ContentType.objects.get_for_model
Opportunity = get_opportunity_model()
Act = commercial.get_act_model()
ActObjectivePattern = commercial.get_pattern_model()
Strategy = commercial.get_strategy_model()


class ApproachesBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'approaches')
    dependencies  = (CommercialApproach,)
    order_by      = 'title'
    verbose_name  = _(u'Commercial approaches')
    # template_name = 'commercial/templatetags/block_approaches.html'
    template_name = 'commercial/bricks/approaches.html'

    # TODO: factorise with assistants blocks (CremeEntity method ??)
    @staticmethod
    def _populate_related_real_entities(comapps, user):
        entities_ids_by_ct = defaultdict(set)

        for comapp in comapps:
            entities_ids_by_ct[comapp.entity_content_type_id].add(comapp.entity_id)

        entities_map = {}
        get_ct = ContentType.objects.get_for_id

        for ct_id, entities_ids in entities_ids_by_ct.iteritems():
            entities_map.update(get_ct(ct_id).model_class().objects.in_bulk(entities_ids))

        for comapp in comapps:
            comapp.creme_entity = entities_map[comapp.entity_id]

    def detailview_display(self, context):
        entity = context['object']
        pk = entity.pk

        if isinstance(entity, get_organisation_model()) and \
           not SettingValue.objects.get(key_id=DISPLAY_ONLY_ORGA_COM_APPROACH_ON_ORGA_DETAILVIEW).value:
            # TODO: regroup the queries
            managers_ids      = entity.get_managers().values_list('id', flat=True)
            employees_ids     = entity.get_employees().values_list('id', flat=True)
            opportunities_ids = Opportunity.objects.filter(relations__type=REL_SUB_TARGETS,
                                                           relations__object_entity=entity,
                                                          ) \
                                                   .values_list('id',flat=True)

            approaches = CommercialApproach.objects.filter(ok_or_in_futur=False,
                                                           entity_id__in=chain([pk], managers_ids, employees_ids, opportunities_ids),
                                                          )
        else:
            approaches = CommercialApproach.get_approaches(pk)

        return self._render(self.get_template_context(
                    context, approaches,
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, pk),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, pk)),
        ))

    def portal_display(self, context, ct_ids):
        btc = self.get_template_context(
                    context,
                    CommercialApproach.get_approaches_for_ctypes(ct_ids),
                    # update_url='/creme_core/blocks/reload/portal/%s/%s/' % (self.id_, list4url(ct_ids)),
                    update_url=reverse('creme_core__reload_portal_blocks', args=(self.id_, list4url(ct_ids))),
         )
        self._populate_related_real_entities(btc['page'].object_list, context['user'])

        return self._render(btc)

    def home_display(self, context):
        btc = self.get_template_context(
                    context, CommercialApproach.get_approaches(),
                    # update_url='/creme_core/blocks/reload/home/%s/' % self.id_,
                    update_url=reverse('creme_core__reload_home_blocks', args=(self.id_,)),
        )
        self._populate_related_real_entities(btc['page'].object_list, context['user'])

        return self._render(btc)


class SegmentsBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'segments')
    dependencies  = (MarketSegment,)
    order_by      = 'name'
    verbose_name  = u'Market segments'
    # template_name = 'commercial/templatetags/block_segments.html'
    template_name = 'commercial/bricks/segments.html'
    configurable  = False
    permission    = 'commercial'  # NB: used by the view creme_core.views.blocks.reload_basic

    def detailview_display(self, context):
        return self._render(self.get_template_context(
                    context, MarketSegment.objects.all(),
                    # update_url='/creme_core/blocks/reload/basic/%s/' % self.id_,
                    update_url=reverse('creme_core__reload_blocks', args=(self.id_,)),
        ))


class SegmentDescriptionsBrick(PaginatedBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'segment_info')
    dependencies  = (MarketSegment,)  # MarketSegmentDescription ??
    verbose_name  = _(u'Market segment descriptions')
    # template_name = 'commercial/templatetags/block_segment_info.html'
    template_name = 'commercial/bricks/segments-info.html'
    target_ctypes = (Strategy,)

    # _SEGMENTDESC_CT_ID = get_ct(MarketSegmentDescription).id

    def detailview_display(self, context):
        strategy = context['object']
        return self._render(self.get_template_context(
                    context, strategy.get_segment_descriptions_list(),
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, strategy.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, strategy.pk)),
                    # ct_id=self._SEGMENTDESC_CT_ID,
                    ct_id=get_ct(MarketSegmentDescription).id,
        ))


class AssetsBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'assets')
    dependencies  = (CommercialAsset,)
    order_by      = 'name'
    verbose_name  = _(u'Commercial assets')
    # template_name = 'commercial/templatetags/block_assets.html'
    template_name = 'commercial/bricks/assets.html'
    target_ctypes = (Strategy,)

    # _ASSET_CT_ID = get_ct(CommercialAsset).id

    def detailview_display(self, context):
        strategy = context['object']
        return self._render(self.get_template_context(
                    context, strategy.assets.all(),
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, strategy.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, strategy.pk)),
                    # ct_id=self._ASSET_CT_ID,
                    ct_id=get_ct(CommercialAsset).id,  # DEPRECATED (use 'objects_ctype.id' instead)
        ))


class CharmsBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'charms')
    dependencies  = (MarketSegmentCharm,)
    order_by      = 'name'
    verbose_name  = _(u'Segment charms')
    # template_name = 'commercial/templatetags/block_charms.html'
    template_name = 'commercial/bricks/charms.html'
    target_ctypes = (Strategy,)

    # _CHARM_CT_ID = get_ct(MarketSegmentCharm).id

    def detailview_display(self, context):
        strategy = context['object']
        return self._render(self.get_template_context(
                    context, strategy.charms.all(),
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, strategy.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, strategy.pk)),
                    # ct_id=self._CHARM_CT_ID,
                    ct_id=get_ct(MarketSegmentCharm).id,  # DEPRECATED (use 'objects_ctype.id' instead)
        ))


class EvaluatedOrgasBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'evaluated_orgas')
    dependencies  = (MarketSegmentCharm,)
    order_by      = 'name'
    verbose_name  = _(u'Evaluated organisations')
    # template_name = 'commercial/templatetags/block_evalorgas.html'
    template_name = 'commercial/bricks/evaluated-organisations.html'
    target_ctypes = (Strategy,)

    def detailview_display(self, context):
        strategy = context['object']

        return self._render(self.get_template_context(
                context, strategy.evaluated_orgas.all(),
                # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, strategy.pk),
                update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, strategy.pk)),
        ))


class AssetsMatrixBrick(Brick):
    id_           = Brick.generate_id('commercial', 'assets_matrix')
    # dependencies  = (CommercialAsset,) #useless (custom reload view....)
    verbose_name  = u'Assets / segments matrix'
    # template_name = 'commercial/templatetags/block_assets_matrix.html'
    template_name = 'commercial/bricks/assets-matrix.html'
    configurable  = False

    def detailview_display(self, context):
        # NB: credentials are OK : we are sure to use the custom relaod view if 'strategy' & 'orga' are in the context
        strategy = context['strategy']
        orga = context['orga']
        return self._render(self.get_template_context(
                        context,
                        assets=strategy.get_assets_list(),
                        segment_info=strategy.get_segment_descriptions_list(),
                        totals=strategy.get_assets_totals(orga),
                        # update_url='/commercial/blocks/assets_matrix/%s/%s/' % (strategy.pk, orga.pk),
                        update_url=reverse('commercial__reload_assets_matrix', args=(strategy.id, orga.id)),
                       )
                    )


class CharmsMatrixBrick(Brick):
    id_           = Brick.generate_id('commercial', 'charms_matrix')
    # dependencies  = (MarketSegmentCharm,) #useless (custom reload view....)
    verbose_name  = u'Charms / segments matrix'
    # template_name = 'commercial/templatetags/block_charms_matrix.html'
    template_name = 'commercial/bricks/charms-matrix.html'
    configurable  = False

    def detailview_display(self, context):
        # NB: credentials are OK : we are sure to use the custom relaod view if 'strategy' & 'orga' are in the context
        strategy = context['strategy']
        orga = context['orga']
        return self._render(self.get_template_context(
                        context,
                        charms=strategy.get_charms_list(),
                        segment_info=strategy.get_segment_descriptions_list(),  # TODO: remove in 1.8
                        totals=strategy.get_charms_totals(orga),
                        # update_url='/commercial/blocks/charms_matrix/%s/%s/' % (strategy.pk, orga.pk),
                        update_url=reverse('commercial__reload_charms_matrix', args=(strategy.pk, orga.pk),)
                       )
                    )


class AssetsCharmsMatrixBrick(Brick):
    id_           = Brick.generate_id('commercial', 'assets_charms_matrix')
    # dependencies  = (CommercialAsset, MarketSegmentCharm,) #useless (custom reload view....)
    verbose_name  = u'Assets / Charms segments matrix'
    # template_name = 'commercial/templatetags/block_assets_charms_matrix.html'
    template_name = 'commercial/bricks/assets-charms-matrix.html'
    configurable  = False

    def detailview_display(self, context):
        # NB: credentials are OK : we are sure to use the custom relaod view if 'strategy' & 'orga' are in the context
        strategy = context['strategy']
        orga = context['orga']
        return self._render(self.get_template_context(
                        context,
                        segment_info=strategy.get_segment_descriptions_list(),
                        # update_url='/commercial/blocks/assets_charms_matrix/%s/%s/' % (strategy.pk, orga.pk),
                        update_url=reverse('commercial__reload_assets_charms_matrix', args=(strategy.pk, orga.pk)),
                       )
                    )


class ActObjectivesBrick(QuerysetBrick):
    id_           = QuerysetBrick.generate_id('commercial', 'objectives')
    dependencies  = (ActObjective,)
    order_by      = 'name'
    verbose_name  = _(u'Objectives of a Commercial Action')
    # template_name = 'commercial/templatetags/block_objectives.html'
    template_name = 'commercial/bricks/objectives.html'
    target_ctypes = (Act,)

    # _OBJECTIVE_CT_ID = get_ct(ActObjective).id

    def detailview_display(self, context):
        act_id = context['object'].id
        # TODO: pre-populate EntityFilters ??
        return self._render(self.get_template_context(
                    context,
                    # NB: "act.objectives.all()" causes a strange additional query...
                    ActObjective.objects.filter(act=act_id),
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, act_id),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, act_id)),
                    # ct_id=self._OBJECTIVE_CT_ID,
                    ct_id=get_ct(ActObjective).id,  # DEPRECATED (use 'objects_ctype.id' instead)
        ))


class RelatedOpportunitiesBrick(PaginatedBrick):
    id_           = PaginatedBrick.generate_id('commercial', 'opportunities')
    dependencies  = (Relation, Opportunity)
    relation_type_deps = (REL_OBJ_COMPLETE_GOAL,)
    verbose_name  = _(u'Opportunities related to a Commercial Action')
    template_name = 'commercial/bricks/opportunities.html'
    target_ctypes = (Act,)

    def detailview_display(self, context):
        act = context['object']

        return self._render(self.get_template_context(
                    context, act.get_related_opportunities(),
                    predicate_id=REL_OBJ_COMPLETE_GOAL,
        ))


class PatternComponentsBrick(Brick):
    id_           = Brick.generate_id('commercial', 'pattern_components')
    dependencies  = (ActObjectivePatternComponent,)
    verbose_name  = _(u'Components of an Objective Pattern')
    # template_name = 'commercial/templatetags/block_components.html'
    template_name = 'commercial/bricks/components.html'
    target_ctypes = (ActObjectivePattern,)

    # _PATTERNCOMP_CT_ID = get_ct(ActObjectivePatternComponent).id

    def detailview_display(self, context):
        pattern = context['object']
        flattened_tree = []

        def explore_tree(components, deep):
            for comp in components:
                comp.deep = deep
                flattened_tree.append(comp)
                explore_tree(comp.get_children(), deep + 1)

        explore_tree(pattern.get_components_tree(), 0)

        return self._render(self.get_template_context(
                    context,
                    components=flattened_tree,
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, pattern.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks', args=(self.id_, pattern.id)),
                    # ct_id=self._PATTERNCOMP_CT_ID,
                    ct_id=get_ct(ActObjectivePatternComponent).id,
        ))

# del get_ct