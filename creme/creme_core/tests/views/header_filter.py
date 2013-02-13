# -*- coding: utf-8 -*-

try:
    from django.core.serializers.json import simplejson
    from django.contrib.auth.models import User
    from django.contrib.contenttypes.models import ContentType

    from creme_core.models import HeaderFilter, HeaderFilterItem, CremeEntity, RelationType, CustomField
    from creme_core.models.header_filter import HFI_FIELD, HFI_RELATION, HFI_CUSTOM, HFI_FUNCTION
    from creme_core.tests.views.base import ViewsTestCase

    from persons.models import Contact, Organisation
except Exception as e:
    print 'Error in <%s>: %s' % (__name__, e)


__all__ = ('HeaderFilterViewsTestCase', )


class HeaderFilterViewsTestCase(ViewsTestCase):
    DELETE_URL = '/creme_core/header_filter/delete'

    @classmethod
    def setUpClass(cls):
        cls.populate('creme_config')
        cls.contact_ct = ContentType.objects.get_for_model(Contact)

        HeaderFilterItem.objects.all().delete()
        HeaderFilter.objects.all().delete()

    def _build_add_url(self, ctype):
        return '/creme_core/header_filter/add/%s' % ctype.id

    def _build_edit_url(self, hf):
        return '/creme_core/header_filter/edit/%s' % hf.id

    def _build_get4ctype_url(self, ctype):
        return '/creme_core/header_filter/get_for_ctype/%s' % ctype.id

    def _find_field_index(self, formfield, name):
        for i, (fname, fvname) in enumerate(formfield.choices):
            if fname == name:
                return i

        self.fail('No "%s" field' % name)

    def test_create01(self):
        self.login()

        ct = ContentType.objects.get_for_model(CremeEntity)
        self.assertEqual(0, HeaderFilter.objects.filter(entity_type=ct).count())

        uri = self._build_add_url(ct)
        response = self.client.get(uri)
        self.assertEqual(200, response.status_code)

        with self.assertNoException():
            form = response.context['form']
            fields_field = form.fields['fields']

        created_index = self._find_field_index(fields_field, 'created')
        name = 'DefaultHeaderFilter'
        response = self.client.post(uri,
                                    data={'name':                            name,
                                          'fields_check_%s' % created_index: 'on',
                                          'fields_value_%s' % created_index: 'created',
                                          'fields_order_%s' % created_index: 1,
                                         }
                                   )
        self.assertNoFormError(response, status=302)

        hfilters = HeaderFilter.objects.filter(entity_type=ct)
        self.assertEqual(1, len(hfilters))

        hfilter = hfilters[0]
        self.assertEqual(name, hfilter.name)
        self.assertIsNone(hfilter.user)

        hfitems = hfilter.header_filter_items.all()
        self.assertEqual(1, len(hfitems))

        hfitem = hfitems[0]
        self.assertEqual('created',        hfitem.name)
        self.assertEqual(1,                hfitem.order)
        self.assertEqual(HFI_FIELD,        hfitem.type)
        self.assertEqual('created__range', hfitem.filter_string)
        self.assertIs(hfitem.is_hidden, False)

    def test_create02(self):
        self.login()

        ct = self.contact_ct
        loves, loved = RelationType.create(('test-subject_love', u'Is loving'),
                                           ('test-object_love',  u'Is loved by')
                                          )
        customfield = CustomField.objects.create(name=u'Size (cm)', field_type=CustomField.INT, content_type=ct)
        prop_funcfield = Contact.function_fields.get('get_pretty_properties')

        uri = self._build_add_url(ct)
        response = self.client.get(uri)

        with self.assertNoException():
            fields = response.context['form'].fields
            fields_field    = fields['fields']
            cfields_field   = fields['custom_fields']
            rtypes_field    = fields['relations']
            funfields_field = fields['functions']

        field_name = 'first_name'
        firstname_index = self._find_field_index(fields_field, field_name)
        cfield_index    = self._find_field_index(cfields_field, customfield.id)
        loves_index     = self._find_field_index(rtypes_field, loves.id)
        self._find_field_index(funfields_field, prop_funcfield.name)
        name = 'DefaultHeaderFilter'
        response = self.client.post(uri, follow=True,
                                    data={'name': name,
                                          'user': self.user.id,

                                          'fields_check_%s' % firstname_index: 'on',
                                          'fields_value_%s' % firstname_index: field_name,
                                          'fields_order_%s' % firstname_index: 1,

                                          'custom_fields_check_%s' % cfield_index: 'on',
                                          'custom_fields_value_%s' % cfield_index: customfield.id,
                                          'custom_fields_order_%s' % cfield_index: 1,

                                          'relations_check_%s' % loves_index: 'on',
                                          'relations_value_%s' % loves_index: loves.id,
                                          'relations_order_%s' % loves_index: 1,

                                          'functions_check_%s' % loves_index: 'on',
                                          'functions_value_%s' % loves_index: prop_funcfield.name,
                                          'functions_order_%s' % loves_index: 1,
                                         }
                                   )
        self.assertNoFormError(response)

        hfilter = self.get_object_or_fail(HeaderFilter, name=name)
        self.assertEqual(self.user, hfilter.user)

        hfitems = hfilter.header_filter_items.order_by('order')
        self.assertEqual(4, len(hfitems))

        hfitem = hfitems[0]
        self.assertEqual(field_name, hfitem.name)
        self.assertEqual(1,          hfitem.order)
        self.assertEqual(HFI_FIELD,  hfitem.type)

        hfitem = hfitems[1]
        self.assertEqual(str(customfield.id), hfitem.name)
        self.assertEqual(2,                   hfitem.order)
        self.assertEqual(HFI_CUSTOM,          hfitem.type)

        hfitem = hfitems[2]
        self.assertEqual(str(loves.id), hfitem.name)
        self.assertEqual(3,             hfitem.order)
        self.assertEqual(HFI_RELATION,  hfitem.type)

        hfitem = hfitems[3]
        self.assertEqual(prop_funcfield.name, hfitem.name)
        self.assertEqual(4,                   hfitem.order)
        self.assertEqual(HFI_FUNCTION,        hfitem.type)

    def test_create03(self):
        "Check app credentials"
        self.login(is_superuser=False)

        uri = self._build_add_url(self.contact_ct)
        self.assertGET404(uri)

        self.role.allowed_apps = ['persons']
        self.role.save()

        self.assertGET200(uri)

    def test_edit01(self):
        "Not editable"
        self.login()

        hf = HeaderFilter.create(pk='tests-hf_entity', name='Entity view', model=CremeEntity, is_custom=False)
        hf.set_items([HeaderFilterItem.build_4_field(model=CremeEntity, name='created')])

        self.assertGET404(self._build_edit_url(hf))

    def test_edit02(self):
        self.login()

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view', model=Contact, is_custom=True)
        hf.set_items([HeaderFilterItem.build_4_field(model=Contact, name='first_name')])

        uri = self._build_edit_url(hf)
        response = self.client.get(uri)
        self.assertEqual(200, response.status_code)

        with self.assertNoException():
            fields_field = response.context['form'].fields['fields']

        first_name_index  = None
        last_name_index = None
        for i, (fname, fvname) in enumerate(fields_field.choices):
            if   fname == 'first_name': first_name_index = i
            elif fname == 'last_name':  last_name_index  = i

        self.assertIsNotNone(first_name_index, 'No "first_name" field')
        self.assertIsNotNone(last_name_index,  'No "last_name" field')

        name = 'Entity view v2'
        response = self.client.post(uri,
                                    data={'name':                               name,
                                          'fields_check_%s' % first_name_index: 'on',
                                          'fields_value_%s' % first_name_index: 'first_name',
                                          'fields_order_%s' % first_name_index: 1,
                                          'fields_check_%s' % last_name_index:  'on',
                                          'fields_value_%s' % last_name_index:  'last_name',
                                          'fields_order_%s' % last_name_index:  2,
                                         }
                                   )
        self.assertNoFormError(response, status=302)

        hf = HeaderFilter.objects.get(pk=hf.id)
        self.assertEqual(name, hf.name)

        hfitems = hf.header_filter_items.order_by('order')
        self.assertEqual(2,            len(hfitems))
        self.assertEqual('first_name', hfitems[0].name)
        self.assertEqual('last_name',  hfitems[1].name)

    def test_edit03(self):
        "Can not edit HeaderFilter that belongs to another user"
        self.login(is_superuser=False)

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view', model=Contact, is_custom=True, user=self.other_user)
        self.assertGET404(self._build_edit_url(hf))

    def test_edit04(self):
        "User do not have the app credentials"
        self.login(is_superuser=False)

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view', model=Contact, is_custom=True, user=self.user)
        self.assertGET404(self._build_edit_url(hf))

    def test_delete01(self):
        self.login()

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view', model=Contact, is_custom=True)
        hf.set_items([HeaderFilterItem.build_4_field(model=Contact, name='first_name')])
        self.assertPOST200(self.DELETE_URL, follow=True, data={'id': hf.id})
        self.assertEqual(0, HeaderFilter.objects.filter(pk=hf.id).count())
        self.assertEqual(0, HeaderFilterItem.objects.filter(header_filter=hf.id).count())

    def test_delete02(self):
        "Not custom -> undeletable"
        self.login()

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view', model=Contact, is_custom=False)
        self.client.post(self.DELETE_URL, data={'id': hf.id})
        self.assertEqual(1, HeaderFilter.objects.filter(pk=hf.id).count())

    def test_delete03(self):
        "Belongs to another user"
        self.login(is_superuser=False)

        self.role.allowed_apps = ['persons']
        self.role.save()

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view',
                                 model=Contact, is_custom=True, user=self.other_user,
                                )
        self.client.post(self.DELETE_URL, data={'id': hf.id})
        self.assertEqual(1, HeaderFilter.objects.filter(pk=hf.id).count())

    def test_delete04(self):
        "Belongs to my team -> ok"
        self.login()

        my_team = User.objects.create(username='TeamTitan', is_team=True)
        my_team.teammates = [self.user]

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view',
                                 model=Contact, is_custom=True, user=my_team,
                                )
        self.assertPOST200(self.DELETE_URL, data={'id': hf.id}, follow=True)
        self.assertEqual(0, HeaderFilter.objects.filter(pk=hf.id).count())

    def test_delete05(self): #belongs to a team (not mine) -> ko
        self.login(is_superuser=False)

        self.role.allowed_apps = ['persons']
        self.role.save()

        a_team = User.objects.create(username='TeamTitan', is_team=True)
        a_team.teammates = [self.other_user]

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view',
                                 model=Contact, is_custom=True, user=a_team,
                                )
        self.client.post(self.DELETE_URL, data={'id': hf.id}, follow=True)
        self.assertEqual(1, HeaderFilter.objects.filter(pk=hf.id).count())

    def test_delete06(self):
        "Logged as super user"
        self.login()

        hf = HeaderFilter.create(pk='tests-hf_contact', name='Contact view',
                                 model=Contact, is_custom=True, user=self.other_user,
                                )
        self.client.post(self.DELETE_URL, data={'id': hf.id})
        self.assertEqual(0, HeaderFilter.objects.filter(pk=hf.id).count())

    def test_hfilters_for_ctype01(self):
        self.login()

        response = self.client.get(self._build_get4ctype_url(self.contact_ct))
        self.assertEqual(200, response.status_code)
        self.assertEqual([], simplejson.loads(response.content))

    def test_hfilters_for_ctype02(self):
        self.login()

        create_hf = HeaderFilter.create
        name01 = 'Contact view01'
        name02 = 'Contact view02'
        hf01 = create_hf(pk='tests-hf_contact01', name=name01,      model=Contact,      is_custom=False)
        hf02 = create_hf(pk='tests-hf_contact02', name=name02,      model=Contact,      is_custom=True)
        create_hf(pk='tests-hf_orga01',           name='Orga view', model=Organisation, is_custom=True)

        response = self.client.get(self._build_get4ctype_url(self.contact_ct))
        self.assertEqual(200, response.status_code)
        self.assertEqual([[hf01.id, name01], [hf02.id, name02]], simplejson.loads(response.content))

    def test_hfilters_for_ctype03(self):
        self.login(is_superuser=False)
        self.assertGET403(self._build_get4ctype_url(self.contact_ct))
