# -*- coding: utf-8 -*-

try:
    from datetime import datetime

    from django.contrib.contenttypes.models import ContentType

    from assistants.models import Action
    from assistants.tests.base import AssistantsTestCase
except Exception as e:
    print 'Error in <%s>: %s' % (__name__, e)


__all__ = ('ActionTestCase',)


class ActionTestCase(AssistantsTestCase):
    def _create_action(self, deadline, title='TITLE', descr='DESCRIPTION', reaction='REACTION', entity=None, user=None):
        entity = entity or self.entity
        user   = user or self.user
        response = self.client.post('/assistants/action/add/%s/' % entity.id,
                                    data={'user':              user.pk,
                                          'title':             title,
                                          'description':       descr,
                                          'expected_reaction': reaction,
                                          'deadline':          deadline
                                         }
                                   )
        self.assertEqual(200, response.status_code)
        self.assertNoFormError(response)

        return self.get_object_or_fail(Action, title=title, description=descr)

    def test_create(self):
        self.assertFalse(Action.objects.exists())

        response = self.client.get('/assistants/action/add/%s/' % self.entity.id)
        self.assertEqual(200, response.status_code)

        title    = 'TITLE'
        descr    = 'DESCRIPTION'
        reaction = 'REACTION'
        deadline = '2010-12-24'
        action = self._create_action(deadline, title, descr, reaction)

        self.assertEqual(title,     action.title)
        self.assertEqual(descr,     action.description)
        self.assertEqual(reaction,  action.expected_reaction)
        self.assertEqual(self.user, action.user)

        self.assertEqual(self.entity.entity_type_id, action.entity_content_type_id)
        self.assertEqual(self.entity.id,             action.entity_id)
        self.assertEqual(self.entity.id,             action.creme_entity.id)

        self.assertLess((datetime.now() - action.creation_date).seconds, 10)
        self.assertEqual(datetime(year=2010, month=12, day=24), action.deadline)

    def test_edit(self):
        title    = 'TITLE'
        descr    = 'DESCRIPTION'
        reaction = 'REACTION'
        action = self._create_action('2010-12-24', title, descr, reaction)

        url = '/assistants/action/edit/%s/' % action.id
        self.assertEqual(200, self.client.get(url).status_code)

        title    += '_edited'
        descr    += '_edited'
        reaction += '_edited'
        deadline = '2011-11-25'
        response = self.client.post(url, data={'user':              self.user.pk,
                                               'title':             title,
                                               'description':       descr,
                                               'expected_reaction': reaction,
                                               'deadline':          deadline,
                                               'deadline_time':     '17:37:00',
                                              }
                                   )
        self.assertEqual(200, response.status_code)
        self.assertNoFormError(response)

        action = self.refresh(action)
        self.assertEqual(title,    action.title)
        self.assertEqual(descr,    action.description)
        self.assertEqual(reaction, action.expected_reaction)
        self.assertEqual(datetime(year=2011, month=11, day=25, hour=17, minute=37), action.deadline)

    def test_delete01(self): #delete related entity
        action = self._create_action('2010-12-24', 'title', 'descr', 'reaction')
        self.entity.delete()
        self.assertFalse(Action.objects.filter(pk=action.pk).exists())

    def test_delete02(self):
        action = self._create_action('2010-12-24', 'title', 'descr', 'reaction')
        ct = ContentType.objects.get_for_model(Action)
        response = self.client.post('/creme_core/entity/delete_related/%s' % ct.id, data={'id': action.id})
        self.assertEqual(302, response.status_code)
        self.assertEqual(0,   Action.objects.count())

    def test_validate(self):
        action = self._create_action('2010-12-24', 'title', 'descr', 'reaction')
        self.assertFalse(action.is_ok)
        self.assertIsNone(action.validation_date)

        self.assertEqual(302, self.client.post('/assistants/action/validate/%s/' % action.id).status_code)

        action = self.refresh(action)
        self.assertTrue(action.is_ok)
        self.assertLess((datetime.now() - action.validation_date).seconds, 10)

    def test_merge(self):
        def creator(contact01, contact02):
            create = self._create_action
            create('2011-2-9',  'Fight',      'I have trained', 'I expect a fight',    entity=contact01)
            create('2011-2-10', 'Rendezvous', 'I have flower',  'I want a rendezvous', entity=contact02)
            self.assertEqual(2, Action.objects.count())

        def assertor(contact01):
            actions = Action.objects.all()
            self.assertEqual(2, len(actions))

            for action in actions:
                self.assertEqual(contact01, action.creme_entity)

        self.aux_test_merge(creator, assertor)

    #TODO: improve block reloading tests with several blocks
