# -*- coding: utf-8 -*-

try:
    from django.utils.translation import ugettext as _

    from creme_core.models import SearchConfigItem, SearchField
    from creme_core.tests.base import CremeTestCase

    from persons.models import Contact, Organisation
except Exception as e:
    print 'Error in <%s>: %s' % (__name__, e)


__all__ = ('SearchConfigTestCase', )


class SearchConfigTestCase(CremeTestCase):
    @classmethod
    def setUpClass(cls):
        SearchConfigItem.objects.all().delete()

    def test_create_if_needed01(self):
        self.assertEqual(0, SearchConfigItem.objects.count())
        self.assertEqual(0, SearchField.objects.count())

        SearchConfigItem.create_if_needed(Contact, ['first_name', 'last_name'])
        sc_items = SearchConfigItem.objects.all()
        self.assertEqual(1, len(sc_items))

        sc_item = sc_items[0]
        self.assertEqual(Contact, sc_item.content_type.model_class())
        self.assertIsNone(sc_item.user)

        sfields = SearchField.objects.filter(search_config_item=sc_item).order_by('id')
        self.assertEqual(2, len(sfields))

        fn_field = sfields[0]
        self.assertEqual('first_name',     fn_field.field)
        self.assertEqual(_(u'First name'), fn_field.field_verbose_name)
        self.assertEqual(1,                fn_field.order)

        ln_field = sfields[1]
        self.assertEqual('last_name',     ln_field.field)
        self.assertEqual(_(u'Last name'), ln_field.field_verbose_name)
        self.assertEqual(2,               ln_field.order)

        SearchConfigItem.create_if_needed(Contact, ['first_name', 'last_name'])
        self.assertEqual(1, SearchConfigItem.objects.count())

        sc_item = self.refresh(sc_item)
        self.assertEqual([(fn_field.id, fn_field.field), (ln_field.id, ln_field.field)],
                         list(SearchField.objects.filter(search_config_item=sc_item).values_list('id', 'field'))
                        )

    def test_create_if_needed02(self): #with user
        self.login()
        user = self.user

        sc_item = SearchConfigItem.create_if_needed(Organisation, ['name'], user)
        self.assertIsInstance(sc_item, SearchConfigItem)

        self.assertEqual(1, SearchConfigItem.objects.count())

        self.assertEqual(Organisation, sc_item.content_type.model_class())
        self.assertEqual(user,         sc_item.user)

    def test_create_if_needed03(self):
        "Invalid fields"
        sc_item = SearchConfigItem.create_if_needed(Contact, ['invalid_field', 'first_name'])

        sfields = SearchField.objects.filter(search_config_item=sc_item)
        self.assertEqual(1, len(sfields))

        fn_field = sfields[0]
        self.assertEqual('first_name', fn_field.field)
        self.assertEqual(1,            fn_field.order)

    def test_get_fields(self):
        sc_item = SearchConfigItem.create_if_needed(Organisation, ['name', 'phone'])

        with self.assertNumQueries(1):
            fields = sc_item.get_fields()

        self.assertEqual(fields, list(SearchField.objects.filter(search_config_item=sc_item)))

        with self.assertNumQueries(0):
            fields2 = sc_item.get_fields()

        self.assertIs(fields, fields2)

    def test_populate_searchfields(self):
        create_if_needed = SearchConfigItem.create_if_needed
        sc_item1 = create_if_needed(Organisation, ['name', 'phone'])
        sc_item2 = create_if_needed(Contact,      ['first_name', 'last_name'])

        with self.assertNumQueries(1):
            SearchConfigItem.populate_searchfields([sc_item1, sc_item2])

        with self.assertNumQueries(0):
            fields1 = sc_item1.get_fields()
            fields2 = sc_item2.get_fields()

        sc_filter = SearchField.objects.filter
        self.assertEqual(fields1, list(sc_filter(search_config_item=sc_item1)))
        self.assertEqual(fields2, list(sc_filter(search_config_item=sc_item2)))
