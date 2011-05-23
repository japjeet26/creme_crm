# -*- coding: utf-8 -*-

from sys import exc_info
from traceback import format_exception

from django.forms.util import ValidationError
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from creme_core import autodiscover
from creme_core.forms.fields import *
from creme_core.forms.entity_filter import *
from creme_core.utils import creme_entity_content_types
from creme_core.models import *
from creme_core.constants import REL_SUB_RELATED_TO, REL_SUB_HAS
from creme_core.tests.base import CremeTestCase

from persons.models import Organisation, Contact, Address
from persons.constants import REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY, REL_SUB_EMPLOYED_BY


def format_stack():
    exc_type, exc_value, exc_traceback = exc_info()
    return ''.join(format_exception(exc_type, exc_value, exc_traceback))

def format_function(func):
    return func.__module__ + '.' + func.__name__.lstrip('<').rstrip('>') + '()' if func else 'None'


class FieldTestCase(CremeTestCase):
    def assertFieldRaises(self, exception, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception, e:
            return (e, format_stack())

        exception_name = exception.__name__ if hasattr(exception, '__name__') else str(exception)
        self.fail("%s not raised" % exception_name)

    def assertFieldValidationError(self, field, key, func, *args, **kwargs):
        message_args = kwargs.pop('message_args', {})   # pop error message args from kwargs
        err, stack = self.assertFieldRaises(ValidationError, func, *args, **kwargs)
        message = unicode(field().error_messages[key] % message_args)

        if not hasattr(err, 'messages'):
            self.fail('unexpected empty message instead of "%s"\nerror : %s' % (message, stack))

        if message != err.messages[0]:
            self.fail('unexpected message "%s" instead of "%s"\nerror : %s' % (err.messages[0], message, stack))


class JSONFieldTestCase(FieldTestCase):
    def test_clean_empty_required(self):
        field = JSONField(required=True)
        self.assertFieldValidationError(JSONField, 'required', field.clean, None)

    def test_clean_empty_not_required(self):
        field = JSONField(required=False)
        field.clean(None)

    def test_clean_invalid_json(self):
        field = JSONField(required=True)

        self.assertFieldValidationError(JSONField, 'invalidformat', field.clean, '{"unclosed_dict"')
        self.assertFieldValidationError(JSONField, 'invalidformat', field.clean, '["unclosed_list",')
        self.assertFieldValidationError(JSONField, 'invalidformat', field.clean, '["","unclosed_str]')
        self.assertFieldValidationError(JSONField, 'invalidformat', field.clean, '["" "comma_error"]')

    def test_clean_valid(self):
        field = JSONField(required=True)
        field.clean('{"ctype":"12","entity":"1"}')

    def test_format_empty_to_json(self):
        field = JSONField()
        self.assertEquals('""', field.from_python(''))

    def test_format_string_to_json(self):
        field = JSONField()
        self.assertEquals('"this is a string"', field.from_python('this is a string'))

    def test_format_object_to_json(self):
        field = JSONField()
        self.assertEquals('{"ctype": "12", "entity": "1"}', field.from_python({"ctype":"12", "entity":"1"}))


def get_field_entry_pair(ctypemodel, model):
    contact_ctype = ContentType.objects.get_for_model(ctypemodel)
    contact = model.objects.all()[0]
    return (contact_ctype, contact)


class GenericEntityFieldTestCase(FieldTestCase):
    def test_models_ctypes(self):
        field = GenericEntityField(models=[Organisation, Contact, Address])
        self.assertEquals(3, len(field.get_ctypes()))
        self.assertEquals(ContentType.objects.get_for_model(Organisation), field.get_ctypes()[0])
        self.assertEquals(ContentType.objects.get_for_model(Contact), field.get_ctypes()[1])
        self.assertEquals(ContentType.objects.get_for_model(Address), field.get_ctypes()[2])

    def test_default_ctypes(self):
        autodiscover()

        field = GenericEntityField()
        self.assertTrue(len(field.get_ctypes()) > 0)
        self.assertEquals(list(creme_entity_content_types()), field.get_ctypes())

    def test_format_object(self):
        self.populate('creme_core', 'persons')

        field = GenericEntityField(models=[Organisation, Contact, Address])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)

        self.assertEquals('{"ctype": 12, "entity": 1}', field.from_python({"ctype":12, "entity":1}))
        self.assertEquals('{"ctype": %s, "entity": %s}' % (contact_ctype.pk, contact.pk), field.from_python(contact))

    def test_clean_empty_required(self):
        field = GenericEntityField(required=True)
        self.assertFieldValidationError(GenericEntityField, 'required', field.clean, None)
        self.assertFieldValidationError(GenericEntityField, 'required', field.clean, "{}")

    def test_clean_empty_not_required(self):
        field = GenericEntityField(required=False)
        field.clean(None)

    def test_clean_invalid_json(self):
        field = GenericEntityField(required=False)
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '{"ctype":"12","entity":"1"')

    def test_clean_invalid_data_type(self):
        field = GenericEntityField(required=False)
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '"this is a string"')
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, "[]")

    def test_clean_invalid_data(self):
        field = GenericEntityField(required=False)
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '{"entity":"1"}')
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '{"ctype":"12"}')
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '{"ctype":"notanumber","entity":"1"}')
        self.assertFieldValidationError(GenericEntityField, 'invalidformat', field.clean, '{"ctype":"12","entity":"notanumber"}')

    # data injection : use a correct content entry (content type and id), but content type not in field list...
    def test_clean_unallowed_ctype(self):
        self.populate('creme_core', 'persons')

        field = GenericEntityField(models=[Organisation, Address])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)

        value = '{"ctype":"%s","entity":"%s"}' % (contact_ctype.pk, contact.pk)

        self.assertFieldValidationError(GenericEntityField, 'ctypenotallowed', field.clean, value)

    # data injection : use a contact id with address content type...
    def test_clean_unknown_entity(self):
        self.populate('creme_core', 'persons')

        field = GenericEntityField(models=[Organisation, Contact, Address])

        address_ctype, contact = get_field_entry_pair(Address, Contact)

        value = '{"ctype":"%s","entity":"%s"}' % (address_ctype.pk, contact.pk)

        self.assertFieldValidationError(GenericEntityField, 'doesnotexist', field.clean, value)

    # TODO : complete this test after form right management refactor.
    def test_clean_unallowed_entity(self):
        pass

    # data injection : use an content id with address content type...
    def test_clean_entity(self):
        self.populate('creme_core', 'persons')
        field = GenericEntityField(models=[Organisation, Contact, Address])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)

        value = '{"ctype":"%s","entity":"%s"}' % (contact_ctype.pk, contact.pk)

        self.assertEquals(contact, field.clean(value))


class MultiGenericEntityFieldTestCase(FieldTestCase):
    def test_models_ctypes(self):
        field = MultiGenericEntityField(models=[Organisation, Contact, Address])
        self.assertEquals(3, len(field.get_ctypes()))
        self.assertEquals(ContentType.objects.get_for_model(Organisation), field.get_ctypes()[0])
        self.assertEquals(ContentType.objects.get_for_model(Contact), field.get_ctypes()[1])
        self.assertEquals(ContentType.objects.get_for_model(Address), field.get_ctypes()[2])

    def test_default_ctypes(self):
        autodiscover()

        field = MultiGenericEntityField()
        self.assertTrue(len(field.get_ctypes()) > 0)
        self.assertEquals(list(creme_entity_content_types()), field.get_ctypes())

    def test_format_object(self):
        self.populate('creme_core', 'persons')

        field = MultiGenericEntityField(models=[Organisation, Contact, Address])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        organisation_ctype, organisation = get_field_entry_pair(Organisation, Organisation)

        self.assertEquals('[{"ctype": 12, "entity": 1}, {"ctype": 14, "entity": 5}]', field.from_python([{"ctype":12, "entity":1},
                                                                                                         {"ctype":14, "entity":5}]))
        self.assertEquals('[{"ctype": %s, "entity": %s}, {"ctype": %s, "entity": %s}]' % (contact_ctype.pk, contact.pk,
                                                                                          organisation_ctype.pk, organisation.pk), field.from_python([contact, organisation]))

    def test_clean_empty_required(self):
        field = MultiGenericEntityField(required=True)
        self.assertFieldValidationError(MultiGenericEntityField, 'required', field.clean, None)
        self.assertFieldValidationError(MultiGenericEntityField, 'required', field.clean, "[]")

    def test_clean_empty_not_required(self):
        field = MultiGenericEntityField(required=False)
        field.clean(None)

    def test_clean_invalid_json(self):
        field = MultiGenericEntityField(required=False)
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '{"ctype":"12","entity":"1"')

    def test_clean_invalid_data_type(self):
        field = MultiGenericEntityField(required=False)
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '"this is a string"')
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, "{}")

    def test_clean_invalid_data(self):
        field = MultiGenericEntityField(required=False)
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '[{"entity":"1"}]')
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '[{"ctype":"12"}]')
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '[{"ctype":"notanumber","entity":"1"}]')
        self.assertFieldValidationError(MultiGenericEntityField, 'invalidformat', field.clean, '[{"ctype":"12","entity":"notanumber"}]')

    # data injection : a Contact and an Organisation entries. the Contact one is remove (not in field list)
    def test_clean_unallowed_ctype(self):
        self.populate('creme_core', 'persons')

        field = MultiGenericEntityField(models=[Organisation, Address])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        organisation_ctype, organisation = get_field_entry_pair(Organisation, Organisation)

        value = '[{"ctype":"%s","entity":"%s"}, {"ctype":"%s","entity":"%s"}]' % (contact_ctype.pk, contact.pk,
                                                                                  organisation_ctype.pk, organisation.pk)

        self.assertFieldValidationError(MultiGenericEntityField, 'ctypenotallowed', field.clean, value)

    # data injection : a Contact and an Organisation entries. the Organisation one is removed (invalid content type)
    def test_clean_unknown_entity(self):
        self.populate('creme_core', 'persons')

        field = MultiGenericEntityField(models=[Organisation, Contact, Address])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        organisation_ctype, contact2 = get_field_entry_pair(Organisation, Contact)

        value = '[{"ctype":"%s","entity":"%s"}, {"ctype":"%s","entity":"%s"}]' % (contact_ctype.pk, contact.pk,
                                                                                  organisation_ctype.pk, contact2.pk)

        self.assertFieldValidationError(MultiGenericEntityField, 'doesnotexist', field.clean, value)

    def test_clean_entities(self):
        self.populate('creme_core', 'persons')

        field = MultiGenericEntityField(models=[Organisation, Contact])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        organisation_ctype, organisation = get_field_entry_pair(Organisation, Organisation)

        value = '[{"ctype":"%s","entity":"%s"}, {"ctype":"%s","entity":"%s"}]' % (contact_ctype.pk, contact.pk,
                                                                                  organisation_ctype.pk, organisation.pk)

        entities = field.clean(value)

        self.assertEquals(2, len(entities))

        self.assertEquals(contact, entities[0])
        self.assertEquals(organisation, entities[1])


def populate_good_bad_property_entities(user):
    subject_ptype = CremePropertyType.create(str_pk='test-prop_foobar-subject', text='Subject property')
    object_ptype  = CremePropertyType.create(str_pk='test-prop_foobar-object', text='Contact property')

    bad_subject   = CremeEntity.objects.create(user=user)
    good_subject  = CremeEntity.objects.create(user=user)

    bad_object   = CremeEntity.objects.create(user=user)
    good_object  = CremeEntity.objects.create(user=user)

    CremeProperty.objects.create(type=subject_ptype, creme_entity=good_subject)
    CremeProperty.objects.create(type=object_ptype, creme_entity=good_object)

    return ((good_subject, bad_subject), (good_object, bad_object), (subject_ptype, object_ptype))


class RelationEntityFieldTestCase(FieldTestCase):
    def test_rtypes(self):
        autodiscover()
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        self.assertEquals(2, len(field._get_allowed_rtypes_objects()))

        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_CUSTOMER_OF), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_CUSTOMER_OF))
        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_EMPLOYED_BY), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_EMPLOYED_BY))

    def test_default_rtypes(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField()
        self.assertEquals(2, len(field._get_allowed_rtypes_objects()))

        self.assertEquals(RelationType.objects.get(pk=REL_SUB_RELATED_TO), field._get_allowed_rtypes_objects().get(pk=REL_SUB_RELATED_TO))
        self.assertEquals(RelationType.objects.get(pk=REL_SUB_HAS), field._get_allowed_rtypes_objects().get(pk=REL_SUB_HAS))

    def test_rtypes_property(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField()
        self.assertEquals(2, len(field.allowed_rtypes))

        self.assertEquals(RelationType.objects.get(pk=REL_SUB_RELATED_TO), field._get_allowed_rtypes_objects().get(pk=REL_SUB_RELATED_TO))
        self.assertEquals(RelationType.objects.get(pk=REL_SUB_HAS), field._get_allowed_rtypes_objects().get(pk=REL_SUB_HAS))

        field.allowed_rtypes = [REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY]

        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_CUSTOMER_OF), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_CUSTOMER_OF))
        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_EMPLOYED_BY), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_EMPLOYED_BY))

    def test_clean_empty_required(self):
        field = RelationEntityField(required=True)
        self.assertFieldValidationError(RelationEntityField, 'required', field.clean, None)
        self.assertFieldValidationError(RelationEntityField, 'required', field.clean, "{}")

    def test_clean_empty_not_required(self):
        field = RelationEntityField(required=False)
        field.clean(None)

    def test_clean_invalid_json(self):
        field = RelationEntityField(required=False)
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", "ctype":"12","entity":"1"')

    def test_clean_invalid_data_type(self):
        field = RelationEntityField(required=False)
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '"this is a string"')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '"[]"')

    def test_clean_invalid_data(self):
        field = RelationEntityField(required=False)
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"ctype":"12","entity":"1"}')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"10","entity":"1"}')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", ctype":"12"}')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"notanumber", ctype":"12","entity":"1"}')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", ctype":"notanumber","entity":"1"}')
        self.assertFieldValidationError(RelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", "ctype":"12","entity":"notanumber"}')

    # data injection : use a correct content entry (content type and id), but relation type not in database...
    def test_clean_unknown_rtype(self):
        self.login()
        Contact.objects.create(user=self.user, first_name='Casca', last_name='Miura')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_OBJ_CUSTOMER_OF, contact_ctype.pk, contact.pk)
        self.assertFieldValidationError(RelationEntityField, 'rtypedoesnotexist', field.clean, value)

    # data injection : use a correct content entry (content type and id), but content type not in field list...
    def test_clean_not_allowed_rtype(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_SUB_RELATED_TO, contact_ctype.pk, contact.pk)
        self.assertFieldValidationError(RelationEntityField, 'rtypenotallowed', field.clean, value)

    # data injection : use a correct address entry not accepted by relation type REL_OBJ_EMPLOYED_BY
    def test_clean_ctype_constraint_error(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_OBJ_EMPLOYED_BY, orga_ctype.pk, orga.pk)
        self.assertFieldValidationError(RelationEntityField, 'ctypenotallowed', field.clean, value)

    # data injection : use an organisation id with contact content type. REL_OBJ_EMPLOYED_BY allows contact content type.
    def test_clean_unknown_entity(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        contact_ctype, orga = get_field_entry_pair(Contact, Organisation)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_OBJ_EMPLOYED_BY, contact_ctype.pk, orga.pk)
        self.assertFieldValidationError(RelationEntityField, 'doesnotexist', field.clean, value)

    def test_clean_relation(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_OBJ_EMPLOYED_BY, contact_ctype.pk, contact.pk)
        self.assertEquals((RelationType.objects.get(pk=REL_OBJ_EMPLOYED_BY), contact), field.clean(value))

    def test_clean_ctype_without_constraint(self):
        self.populate('creme_core', 'persons')

        field = RelationEntityField(allowed_rtypes=[REL_SUB_RELATED_TO, REL_SUB_HAS])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (REL_SUB_RELATED_TO, contact_ctype.pk, contact.pk)
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_RELATED_TO), contact), field.clean(value))

    # data injection : use a entity with missing property
    def test_clean_properties_constraint_error(self):
        self.login()
        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object
        subject_ptype, object_ptype = properties

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], [subject_ptype]),
                                               ('test-object_foobar',  'is managed by', [], [object_ptype])
                                              )

        field = RelationEntityField(allowed_rtypes=[rtype.pk])
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (rtype.pk, bad_object.entity_type.pk, bad_object.pk)
        self.assertFieldValidationError(RelationEntityField, 'nopropertymatch', field.clean, value)

    def test_clean_properties_constraint(self):
        self.login()
        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object
        subject_ptype, object_ptype = properties

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], [subject_ptype]),
                                               ('test-object_foobar',  'is managed by', [], [object_ptype])
                                              )

        field = RelationEntityField(allowed_rtypes=[rtype.pk])
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (rtype.pk, good_object.entity_type.pk, good_object.pk)
        self.assertEquals((RelationType.objects.get(pk=rtype.pk), good_object), field.clean(value))

    def test_clean_properties_without_constraint(self):
        self.login()
        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], []),
                                               ('test-object_foobar',  'is managed by', [], [])
                                              )

        field = RelationEntityField(allowed_rtypes=[rtype.pk])
        value = '{"rtype":"%s", "ctype":"%s","entity":"%s"}' % (rtype.pk, bad_object.entity_type.pk, bad_object.pk)
        self.assertEquals((RelationType.objects.get(pk=rtype.pk), bad_object), field.clean(value))


class MultiRelationEntityFieldTestCase(FieldTestCase):
    def test_rtypes(self):
        autodiscover()
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        self.assertEquals(2, len(field._get_allowed_rtypes_objects()))

        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_CUSTOMER_OF), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_CUSTOMER_OF))
        self.assertEquals(RelationType.objects.get(pk=REL_OBJ_EMPLOYED_BY), field._get_allowed_rtypes_objects().get(pk=REL_OBJ_EMPLOYED_BY))

    def test_default_rtypes(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField()
        self.assertTrue(2, len(field._get_allowed_rtypes_objects()))
        self.assertEquals(RelationType.objects.get(pk=REL_SUB_RELATED_TO), field._get_allowed_rtypes_objects().get(pk=REL_SUB_RELATED_TO))
        self.assertEquals(RelationType.objects.get(pk=REL_SUB_HAS), field._get_allowed_rtypes_objects().get(pk=REL_SUB_HAS))

    def test_clean_empty_required(self):
        field = MultiRelationEntityField(required=True)
        self.assertFieldValidationError(MultiRelationEntityField, 'required', field.clean, None)
        self.assertFieldValidationError(MultiRelationEntityField, 'required', field.clean, "[]")

    def test_clean_empty_not_required(self):
        field = MultiRelationEntityField(required=False)
        field.clean(None)

    def test_clean_invalid_json(self):
        field = MultiRelationEntityField(required=False)
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", "ctype":"12","entity":"1"')

    def test_clean_invalid_data_type(self):
        field = MultiRelationEntityField(required=False)
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '"this is a string"')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '"{}"')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '{"rtype":"10", "ctype":"12","entity":"1"}')

    def test_clean_invalid_data(self):
        field = MultiRelationEntityField(required=False)
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"ctype":"12","entity":"1"}]')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"rtype":"10","entity":"1"}]')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"rtype":"10", ctype":"12"}]')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"rtype":"notanumber", ctype":"12","entity":"1"}]')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"rtype":"10", ctype":"notanumber","entity":"1"}]')
        self.assertFieldValidationError(MultiRelationEntityField, 'invalidformat', field.clean, '[{"rtype":"10", "ctype":"12","entity":"notanumber"}]')

    # data injection : use a correct content entry (content type and id), but content type not in field list...
    def test_clean_unknown_rtype(self):
        self.login()
        Contact.objects.create(user=self.user, first_name='Casca', last_name='Miura')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])
        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        value = '[{"rtype":"%s", "ctype":"%s","entity":"%s"}]' % (REL_OBJ_CUSTOMER_OF, contact_ctype.pk, contact.pk)
        self.assertFieldValidationError(RelationEntityField, 'rtypedoesnotexist', field.clean, value)

    # data injection : use a correct content entry (content type and id), but content type not in field list...
    def test_clean_not_allowed_rtype(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        value = '[{"rtype":"%s", "ctype":"%s","entity":"%s"},{"rtype":"%s", "ctype":"%s","entity":"%s"}]' % (
                        REL_SUB_RELATED_TO, contact_ctype.pk, contact.pk,
                        REL_SUB_HAS, orga_ctype.pk, orga.pk,
                    )
        self.assertFieldValidationError(RelationEntityField, 'rtypenotallowed', field.clean, value)

    # data injection : use a correct address entry not accepted by relation type REL_OBJ_EMPLOYED_BY
    def test_clean_ctype_constraint_error(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        value = '[{"rtype":"%s", "ctype":"%s","entity":"%s"},{"rtype":"%s", "ctype":"%s","entity":"%s"}]' % (
                        REL_OBJ_EMPLOYED_BY, orga_ctype.pk, orga.pk,
                        REL_OBJ_CUSTOMER_OF, contact_ctype.pk, contact.pk,
                    )
        self.assertFieldValidationError(MultiRelationEntityField, 'ctypenotallowed', field.clean, value)

    # data injection : use an organisation id with contact content type. REL_OBJ_EMPLOYED_BY allows contact content type.
    def test_clean_unknown_entity(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        value = '[{"rtype":"%s", "ctype":"%s","entity":"%s"},{"rtype":"%s", "ctype":"%s","entity":"%s"}]' % (
                        REL_OBJ_EMPLOYED_BY, contact_ctype.pk, orga.pk,
                        REL_OBJ_CUSTOMER_OF, contact_ctype.pk, contact.pk,
                    )
        self.assertFieldValidationError(MultiRelationEntityField, 'doesnotexist', field.clean, value)

    def test_clean_relations(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_OBJ_CUSTOMER_OF, REL_OBJ_EMPLOYED_BY, REL_SUB_EMPLOYED_BY])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        value = """[{"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"}]""" % (REL_OBJ_EMPLOYED_BY, contact_ctype.pk, contact.pk,
                                                                      REL_OBJ_CUSTOMER_OF, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_EMPLOYED_BY, orga_ctype.pk, orga.pk)

        relations = field.clean(value)
        self.assertEquals(3, len(relations))

        self.assertEquals((RelationType.objects.get(pk=REL_OBJ_EMPLOYED_BY), contact), relations[0])
        self.assertEquals((RelationType.objects.get(pk=REL_OBJ_CUSTOMER_OF), contact), relations[1])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_EMPLOYED_BY), orga), relations[2])

    def test_clean_ctype_without_constraint(self):
        self.populate('creme_core', 'persons')

        field = MultiRelationEntityField(allowed_rtypes=[REL_SUB_RELATED_TO, REL_SUB_HAS])

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        value = """[{"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"}]""" % (REL_SUB_RELATED_TO, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_HAS, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_RELATED_TO, orga_ctype.pk, orga.pk)

        relations = field.clean(value)
        self.assertEquals(3, len(relations))

        self.assertEquals((RelationType.objects.get(pk=REL_SUB_RELATED_TO), contact), relations[0])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_HAS), contact), relations[1])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_RELATED_TO), orga), relations[2])


    # data injection : use a entity with missing property
    def test_clean_properties_constraint_error(self):
        self.login()
        self.populate('creme_core', 'persons')

        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object
        subject_ptype, object_ptype = properties

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], [subject_ptype]),
                                               ('test-object_foobar',  'is managed by', [], [object_ptype])
                                              )

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        field = MultiRelationEntityField(allowed_rtypes=[rtype.pk, REL_SUB_RELATED_TO, REL_SUB_HAS])

        value = """[{"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"}]""" % (rtype.pk, bad_object.entity_type.pk, bad_object.pk,
                                                                      REL_SUB_HAS, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_RELATED_TO, orga_ctype.pk, orga.pk)
        self.assertFieldValidationError(RelationEntityField, 'nopropertymatch', field.clean, value)

    def test_clean_properties_constraint(self):
        self.login()
        self.populate('creme_core', 'persons')

        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object
        subject_ptype, object_ptype = properties

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], [subject_ptype]),
                                               ('test-object_foobar',  'is managed by', [], [object_ptype])
                                              )

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        field = MultiRelationEntityField(allowed_rtypes=[rtype.pk, REL_SUB_RELATED_TO, REL_SUB_HAS])

        value = """[{"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"}]""" % (rtype.pk, good_object.entity_type.pk, good_object.pk,
                                                                      REL_SUB_HAS, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_RELATED_TO, orga_ctype.pk, orga.pk)

        relations = field.clean(value)
        self.assertEquals(3, len(relations))

        self.assertEquals((RelationType.objects.get(pk=rtype.pk), good_object), relations[0])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_HAS), contact), relations[1])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_RELATED_TO), orga), relations[2])

    def test_clean_properties_without_constraint(self):
        self.login()
        self.populate('creme_core', 'persons')

        subject, object, properties = populate_good_bad_property_entities(self.user)

        good_object, bad_object = object

        rtype, sym_rtype = RelationType.create(('test-subject_foobar', 'manages',       [], []),
                                               ('test-object_foobar',  'is managed by', [], [])
                                              )

        contact_ctype, contact = get_field_entry_pair(Contact, Contact)
        orga_ctype, orga = get_field_entry_pair(Organisation, Organisation)

        field = MultiRelationEntityField(allowed_rtypes=[rtype.pk, REL_SUB_RELATED_TO, REL_SUB_HAS])

        value = """[{"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"},
                    {"rtype":"%s", "ctype":"%s","entity":"%s"}]""" % (rtype.pk, bad_object.entity_type.pk, bad_object.pk,
                                                                      rtype.pk, good_object.entity_type.pk, good_object.pk,
                                                                      REL_SUB_HAS, contact_ctype.pk, contact.pk,
                                                                      REL_SUB_RELATED_TO, orga_ctype.pk, orga.pk)

        relations = field.clean(value)
        self.assertEquals(4, len(relations))

        self.assertEquals((RelationType.objects.get(pk=rtype.pk), bad_object), relations[0])
        self.assertEquals((RelationType.objects.get(pk=rtype.pk), good_object), relations[1])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_HAS), contact), relations[2])
        self.assertEquals((RelationType.objects.get(pk=REL_SUB_RELATED_TO), orga), relations[3])


class RegularFieldsConditionsFieldTestCase(FieldTestCase):
    def test_clean_empty_required(self):
        clean = RegularFieldsConditionsField(required=True).clean
        self.assertFieldValidationError(RegularFieldsConditionsField, 'required', clean, None)
        self.assertFieldValidationError(RegularFieldsConditionsField, 'required', clean, "")
        self.assertFieldValidationError(RegularFieldsConditionsField, 'required', clean, "[]")

    def test_clean_empty_not_required(self):
        field = RegularFieldsConditionsField(required=False)

        try:
            field.clean(None)
        except Exception, e:
            self.fail(str(e))

    def test_clean_invalid_data_type(self):
        clean = RegularFieldsConditionsField().clean
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '"this is a string"')
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '"{}"')
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '{"foobar":{"operator":"3","name":"first_name","value":"Rei"}}')

    def test_clean_invalid_data(self):
        clean = RegularFieldsConditionsField(model=Contact).clean
        EQUALS = EntityFilterCondition.EQUALS
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '[{"operator": "%s", "name": "first_name"}]' % EQUALS)
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '[{"operator": "%s", "value": "Rei"}]' % EQUALS)
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '[{"name": "first_name", "value": "Rei"}]')
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidformat', clean, '[{"operator": "notanumber", "name": "first_name", "value": "Rei"}]')

    def test_clean_invalid_field(self):
        clean = RegularFieldsConditionsField(model=Contact).clean
        format_str = '[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]'

        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator':  EntityFilterCondition.EQUALS,
                                                      'name':  '   boobies_size', #<---
                                                      'value':     '90',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'is_deleted',
                                                      'value':    'Faye',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'created',
                                                      'value':    '2011-5-12',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'civility__id',
                                                      'value':    '5',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'image__id',
                                                      'value':    '5',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'image__is_deleted',
                                                      'value':    '5',
                                         })
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidfield', clean,
                                        format_str % {'operator': EntityFilterCondition.IEQUALS,
                                                      'name':     'image__modified',
                                                      'value':    '2011-5-12',
                                         })
        #TODO: M2M

    def test_clean_invalid_operator(self):
        clean = RegularFieldsConditionsField(model=Contact).clean
        self.assertFieldValidationError(RegularFieldsConditionsField, 'invalidoperator', clean,
                                        '[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]' % {
                                            'operator': EntityFilterCondition.EQUALS + 1000, # <--
                                            'name':     'first_name',
                                            'value':    'Nana',
                                         })

    def test_ok01(self):
        clean = RegularFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.IEQUALS
        name = 'first_name'
        value = 'Faye'
        conditions = clean('[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]' % {
                                 'operator': operator,
                                 'name':     name,
                                 'value':    value,
                             })
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_FIELD,           condition.type)
        self.assertEqual(name,                                      condition.name)
        self.assertEqual({'operator': operator, 'values': [value]}, condition.decoded_value)

    def test_ok02(self): #ISNULL -> boolean
        clean = RegularFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.ISNULL
        name = 'description'
        conditions = clean('[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": false}}]' % {
                                 'operator': operator,
                                 'name':     name,
                             })
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_FIELD,           condition.type)
        self.assertEqual(name,                                      condition.name)
        self.assertEqual({'operator': operator, 'values': [False]}, condition.decoded_value)

    def test_ok03(self): #FK field
        clean = RegularFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.ISTARTSWITH
        name = 'civility__title'
        value = 'Miss'
        conditions = clean('[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]' % {
                                 'operator': operator,
                                 'name':     name,
                                 'value':    value,
                             })
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_FIELD,           condition.type)
        self.assertEqual(name,                                      condition.name)
        self.assertEqual({'operator': operator, 'values': [value]}, condition.decoded_value)

    def test_ok04(self): #multivalues
        clean = RegularFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.IENDSWITH
        name = 'last_name'
        values = ['nagi', 'sume']
        conditions = clean('[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]' % {
                                 'operator': operator,
                                 'name':     name,
                                 'value':    ','.join(values) + ',',
                             })
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_FIELD,          condition.type)
        self.assertEqual(name,                                     condition.name)
        self.assertEqual({'operator': operator, 'values': values}, condition.decoded_value)

    def test_ok05(self): #M2M field
        clean = RegularFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.IEQUALS
        name = 'language__name'
        value = 'French'
        conditions = clean('[{"name": "%(name)s", "operator": "%(operator)s", "value": {"type": "%(operator)s", "value": "%(value)s"}}]' % {
                                 'operator': operator,
                                 'name':     name,
                                 'value':    value,
                             })
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_FIELD,           condition.type)
        self.assertEqual(name,                                      condition.name)
        self.assertEqual({'operator': operator, 'values': [value]}, condition.decoded_value)


class DateFieldsConditionsFieldTestCase(FieldTestCase):
    def test_clean_invalid_data(self):
        field = DateFieldsConditionsField(model=Contact)
        self.assertFieldValidationError(DateFieldsConditionsField, 'invalidfield', field.clean,
                                        '[{"field": "first_name", "range": {"type": "next_quarter", "start": "2011-5-12"}}]'
                                       )
        self.assertFieldValidationError(DateFieldsConditionsField, 'invalidformat', field.clean,
                                        '[{"field": "birthday", "range":"not a dict"}]'
                                       )
        self.assertFieldValidationError(DateFieldsConditionsField, 'invaliddaterange', field.clean,
                                       '[{"field": "birthday", "range": {"type":"unknow_range"}}]' #TODO: "start": '' ???
                                       )

        self.assertFieldValidationError(DateFieldsConditionsField, 'emptydates', field.clean,
                                       '[{"field": "birthday", "range": {"type":""}}]'
                                       )
        self.assertFieldValidationError(DateFieldsConditionsField, 'emptydates', field.clean,
                                       '[{"field": "birthday", "range": {"type":"", "start": "", "end": ""}}]'
                                       )

        try:   field.clean('[{"field": "created", "range": {"type": "", "start": "not a date"}}]')
        except ValidationError: pass
        else:  self.fail('No ValidationError')

        try:   field.clean('[{"field": "created", "range": {"type": "", "end": "2011-2-30"}}]') #30 february !!
        except ValidationError: pass
        else:  self.fail('No ValidationError')

    def test_ok01(self):
        field = DateFieldsConditionsField(model=Contact)
        type01 = 'current_year'
        name01 = 'created'
        type02 = 'next_quarter'
        name02 = 'birthday'
        conditions = field.clean('[{"field": "%(name01)s", "range": {"type": "%(type01)s"}},'
                                 ' {"field": "%(name02)s", "range": {"type": "%(type02)s"}}]' % {
                                        'type01': type01,
                                        'name01': name01,
                                        'type02': type02,
                                        'name02': name02,
                                    }
                                )
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_DATEFIELD, condition.type)
        self.assertEqual(name01,                              condition.name)
        self.assertEqual({'name': type01},                    condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_DATEFIELD, condition.type)
        self.assertEqual(name02,                              condition.name)
        self.assertEqual({'name': type02},                    condition.decoded_value)

    def test_ok02(self): #start/end
        field = DateFieldsConditionsField(model=Contact)
        name01 = 'created'
        name02 = 'birthday'
        conditions = field.clean('[{"field": "%(name01)s", "range": {"type": "", "start": "2011-5-12"}},'
                                 ' {"field": "%(name02)s", "range": {"type": "", "end": "2012-6-13"}}]' % {
                                        'name01': name01,
                                        'name02': name02,
                                    }
                                )
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_DATEFIELD,              condition.type)
        self.assertEqual(name01,                                           condition.name)
        self.assertEqual({'start': {'year': 2011, 'month': 5, 'day': 12}}, condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_DATEFIELD,            condition.type)
        self.assertEqual(name02,                                         condition.name)
        self.assertEqual({'end': {'year': 2012, 'month': 6, 'day': 13}}, condition.decoded_value)

    def test_ok03(self): #start + end
        clean = DateFieldsConditionsField(model=Contact).clean
        name = 'modified'
        conditions = clean('[{"field": "%s", "range": {"type": "", "start": "2010-3-24", "end": "2011-7-25"}}]' % name)
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_DATEFIELD, condition.type)
        self.assertEqual(name,                                condition.name)
        self.assertEqual({'start': {'year': 2010, 'month': 3, 'day': 24}, 'end': {'year': 2011, 'month': 7, 'day': 25}},
                         condition.decoded_value
                        )


class CustomFieldsConditionsFieldTestCase(FieldTestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Contact)
        self.custom_field = CustomField.objects.create(name='Size', content_type=ct, field_type=CustomField.INT)

    def test_clean_invalid_data(self):
        field = CustomFieldsConditionsField(model=Contact)
        self.assertFieldValidationError(CustomFieldsConditionsField, 'invalidcustomfield', field.clean,
                                        '[{"field": "2054", "operator": "%(operator)s", "value":"170"}]' % {
                                                'operator': EntityFilterCondition.EQUALS,
                                            }
                                       )
        self.assertFieldValidationError(CustomFieldsConditionsField, 'invalidtype', field.clean,
                                        '[{"field": "%(cfield)s", "operator": "121266", "value":"170"}]' % {
                                                'cfield': self.custom_field.id,
                                            }
                                       )

    def test_ok(self):
        clean = CustomFieldsConditionsField(model=Contact).clean
        operator = EntityFilterCondition.EQUALS
        value = 180
        conditions = clean('[{"field":"%(cfield)s", "operator": "%(operator)s", "value":"%(value)s"}]' % {
                                'cfield':   self.custom_field.id,
                                'operator': operator,
                                'value':    value,
                              }
                          )
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_CUSTOMFIELD, condition.type)
        self.assertEqual(str(self.custom_field.id),             condition.name)
        self.assertEqual({'operator': operator, 'rname': 'customfieldinteger', 'value': unicode(value)},
                         condition.decoded_value
                        )


class DateCustomFieldsConditionsFieldTestCase(FieldTestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Contact)
        self.cfield01 = CustomField.objects.create(name='Day', content_type=ct, field_type=CustomField.DATE)
        self.cfield02 = CustomField.objects.create(name='First flight', content_type=ct, field_type=CustomField.DATE)

    def test_clean_invalid_data(self):
        field = DateCustomFieldsConditionsField(model=Contact)

        self.assertFieldValidationError(DateCustomFieldsConditionsField, 'invalidcustomfield', field.clean,
                                        '[{"field": "2054", "range": {"type": "current_year"}}]'
                                       )

        self.assertFieldValidationError(DateCustomFieldsConditionsField, 'invalidformat', field.clean,
                                        '[{"field": "%s", "range": "not a dict"}]' % self.cfield01.id
                                       )
        self.assertFieldValidationError(DateCustomFieldsConditionsField, 'invaliddaterange', field.clean,
                                       '[{"field": "%s", "range": {"type":"unknow_range"}}]' % self.cfield01.id
                                       )

        self.assertFieldValidationError(DateCustomFieldsConditionsField, 'emptydates', field.clean,
                                       '[{"field": "%s", "range": {"type":""}}]' % self.cfield01.id
                                       )

        self.assertFieldValidationError(DateCustomFieldsConditionsField, 'emptydates', field.clean,
                                       '[{"field": "%s", "range": {"type":"", "start": "", "end": ""}}]' % self.cfield01.id
                                       )

    def test_ok01(self):
        field = DateCustomFieldsConditionsField(model=Contact)
        rtype  = 'current_year'
        conditions = field.clean('[{"field": "%(cfield01)s", "range": {"type": "%(type)s"}},'
                                 ' {"field": "%(cfield02)s", "range": {"type": "", "start": "2011-5-12"}},'
                                 ' {"field": "%(cfield01)s", "range": {"type": "", "end": "2012-6-13"}},'
                                 ' {"field": "%(cfield02)s", "range": {"type": "", "start": "2011-5-12", "end": "2012-6-13"}}]' % {
                                        'type':     rtype,
                                        'cfield01': self.cfield01.id,
                                        'cfield02': self.cfield02.id,
                                    }
                                )
        self.assertEqual(4, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_DATECUSTOMFIELD, condition.type)
        self.assertEqual(str(self.cfield01.id),                     condition.name)
        self.assertEqual({'rname': 'customfielddatetime', 'name': rtype}, condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_DATECUSTOMFIELD, condition.type)
        self.assertEqual(str(self.cfield02.id),                     condition.name)
        self.assertEqual({'rname': 'customfielddatetime', 'start': {'year': 2011, 'month': 5, 'day': 12}},
                         condition.decoded_value
                        )

        condition = conditions[2]
        self.assertEqual(EntityFilterCondition.EFC_DATECUSTOMFIELD, condition.type)
        self.assertEqual(str(self.cfield01.id),                     condition.name)
        self.assertEqual({'rname': 'customfielddatetime', 'end': {'year': 2012, 'month': 6, 'day': 13}},
                         condition.decoded_value
                        )

        condition = conditions[3]
        self.assertEqual(EntityFilterCondition.EFC_DATECUSTOMFIELD, condition.type)
        self.assertEqual(str(self.cfield02.id),                     condition.name)
        self.assertEqual({'rname': 'customfielddatetime',
                          'start': {'year': 2011, 'month': 5, 'day': 12},
                          'end':   {'year': 2012, 'month': 6, 'day': 13},
                         },
                         condition.decoded_value
                        )


class PropertiesConditionsFieldTestCase(FieldTestCase):
    def setUp(self):
        self.ptype01 = CremePropertyType.create('test-prop_active', 'Is active')
        self.ptype02 = CremePropertyType.create('test-prop_cute',   'Is cute', (Contact,))
        self.ptype03 = CremePropertyType.create('test-prop_evil',   'Is evil', (Organisation,))

    def test_clean_empty_required(self):
        field = PropertiesConditionsField(required=True)
        self.assertFieldValidationError(PropertiesConditionsField, 'required', field.clean, None)
        self.assertFieldValidationError(PropertiesConditionsField, 'required', field.clean, "")
        self.assertFieldValidationError(PropertiesConditionsField, 'required', field.clean, "[]")

    def test_clean_empty_not_required(self):
        field = PropertiesConditionsField(required=False)

        try:
            field.clean(None)
        except Exception, e:
            self.fail(str(e))

    def test_clean_invalid_data_type(self):
        field = PropertiesConditionsField(model=Contact)
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '"this is a string"')
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '"{}"')
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '{"foobar":{"ptype":"test-foobar","has":"true"}}')

    def test_clean_invalid_data(self):
        field = PropertiesConditionsField(model=Contact)
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '[{"ptype":"%s"}]' % self.ptype01.id)
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '[{"has":"true"}]')
        #self.assertFieldValidationError(PropertiesConditionsField, 'invalidformat', field.clean, '[{"ptype":"%s","has":"not a boolean"}]' % self.ptype02.id)

    def test_unknown_ptype(self):
        field = PropertiesConditionsField(model=Contact)
        self.assertFieldValidationError(PropertiesConditionsField, 'invalidptype', field.clean, '[{"ptype":"%s","has":"true"}]' % self.ptype03.id)

    def test_ok(self):
        field = PropertiesConditionsField(model=Contact)
        conditions = field.clean('[{"ptype": "%s", "has": true}, {"ptype": "%s", "has": false}]' % (self.ptype01.id, self.ptype02.id))
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_PROPERTY, condition.type)
        self.assertEqual(self.ptype01.id,                    condition.name)
        self.assert_(condition.decoded_value is True)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_PROPERTY, condition.type)
        self.assertEqual(self.ptype02.id,                    condition.name)
        self.assert_(condition.decoded_value is False)


class RelationsConditionsFieldTestCase(FieldTestCase):
    def setUp(self):
        create = RelationType.create
        self.rtype01, self.rtype02 = create(('test-subject_love', u'Is loving', (Contact,)),
                                            ('test-object_love',  u'Is loved by')
                                           )
        self.rtype03, self.srtype04 = create(('test-subject_belong', u'(orga) belongs to (orga)', (Organisation,)),
                                             ('test-object_belong',  u'(orga) has (orga)',        (Organisation,))
                                            )

    def test_clean_empty_required(self):
        field = RelationsConditionsField(required=True)
        self.assertFieldValidationError(RelationsConditionsField, 'required', field.clean, None)
        self.assertFieldValidationError(RelationsConditionsField, 'required', field.clean, "")
        self.assertFieldValidationError(RelationsConditionsField, 'required', field.clean, "[]")

    def test_clean_empty_not_required(self):
        field = RelationsConditionsField(required=False)

        try:
            field.clean(None)
        except Exception, e:
            self.fail(str(e))

    def test_clean_invalid_data_type(self):
        clean = RelationsConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '"this is a string"')
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '"{}"')
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '{"foobar":{"rtype":"test-foobar","has":"true"}}')

    def test_clean_invalid_data(self):
        clean = RelationsConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '[{"rtype":"%s"}]' % self.rtype01.id)
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '[{"has":"true"}]')
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '[{"rtype":"%s","has":"not a boolean"}]' % self.rtype01.id)
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '[{"rtype":"%s","has":"true", "ctype":"not an int"}]' % self.rtype01.id)
        self.assertFieldValidationError(RelationsConditionsField, 'invalidformat', clean, '[{"rtype":"%s","has":"true", "entity":"not an int"}]' % self.rtype01.id)

    def test_unknown_ct(self):
        clean = RelationsConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationsConditionsField, 'invalidct', clean, '[{"rtype":"%s","has":"true", "ctype":"2121545"}]' % self.rtype01.id)

    def test_unknown_entity(self):
        clean = RelationsConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationsConditionsField, 'invalidentity', clean,
                                        '[{"rtype":"%s","has":"true","ctype":"1","entity":"2121545"}]' % self.rtype01.id
                                       )

    def test_ok01(self): #no ct, no object entity
        field = RelationsConditionsField(model=Contact)
        conditions = field.clean('[{"rtype":"%s", "has": true, "ctype": "0", "entity": null},'
                                 ' {"rtype": "%s", "has": false, "ctype": "0", "entity": null}]' % (
                                    self.rtype01.id, self.rtype02.id)
                                )
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_RELATION, condition.type)
        self.assertEqual(self.rtype01.id,                    condition.name)
        self.assertEqual({'has': True},                      condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_RELATION, condition.type)
        self.assertEqual(self.rtype02.id,                    condition.name)
        self.assertEqual({'has': False},                     condition.decoded_value)

    def test_ok02(self): #wanted ct
        field = RelationsConditionsField(model=Contact)
        ct = ContentType.objects.get_for_model(Contact)
        conditions = field.clean('[{"rtype": "%(rtype01)s", "has": true,  "ctype": "%(ct)s", "entity": null},'
                                 ' {"rtype": "%(rtype02)s", "has": false, "ctype": "%(ct)s"}]' % {
                                        'rtype01': self.rtype01.id,
                                        'rtype02': self.rtype02.id,
                                        'ct':      ct.id,
                                    }
                                )
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_RELATION, condition.type)
        self.assertEqual(self.rtype01.id,                    condition.name)
        self.assertEqual({'has': True, 'ct_id': ct.id},      condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_RELATION, condition.type)
        self.assertEqual(self.rtype02.id,                    condition.name)
        self.assertEqual({'has': False, 'ct_id': ct.id},     condition.decoded_value)

    def test_ok03(self): #wanted entity
        self.login()

        naru = Contact.objects.create(user=self.user, first_name='Naru', last_name='Narusegawa')
        field = RelationsConditionsField(model=Contact)
        ct = ContentType.objects.get_for_model(Contact)
        conditions = field.clean('[{"rtype":"%(rtype)s", "has":"true", "ctype":"%(ct)s", "entity":"%(entity)s"}]' % {
                                        'rtype':  self.rtype01.id,
                                        'ct':     ct.id,
                                        'entity': naru.id,
                                    }
                                )
        self.assertEqual(1, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_RELATION,  condition.type)
        self.assertEqual(self.rtype01.id,                     condition.name)
        self.assertEqual({'has': True, 'entity_id': naru.id}, condition.decoded_value)


class RelationSubfiltersConditionsFieldTestCase(FieldTestCase):
    def setUp(self):
        create = RelationType.create
        self.rtype01, self.rtype02 = create(('test-subject_love', u'Is loving', (Contact,)),
                                            ('test-object_love',  u'Is loved by')
                                           )
        self.rtype03, self.srtype04 = create(('test-subject_belong', u'(orga) belongs to (orga)', (Organisation,)),
                                             ('test-object_belong',  u'(orga) has (orga)',        (Organisation,))
                                            )

        self.sub_efilter01 = EntityFilter.create(pk='test-filter01', name='Filter 01', model=Contact)
        self.sub_efilter02 = EntityFilter.create(pk='test-filter02', name='Filter 02', model=Organisation)

    def test_clean_empty_required(self):
        field = RelationsConditionsField(required=True)
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'required', field.clean, None)
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'required', field.clean, "")
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'required', field.clean, "[]")

    def test_clean_invalid_data(self):
        clean = RelationSubfiltersConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'invalidformat', clean, '[{"rtype":"%s"}]' % self.rtype01.id)
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'invalidformat', clean, '[{"has":"true"}]')

    def test_unknown_filter(self):
        clean = RelationSubfiltersConditionsField(model=Contact).clean
        self.assertFieldValidationError(RelationSubfiltersConditionsField, 'invalidfilter', clean,
                                        '[{"rtype": "%(rtype)s", "has": "false", "ctype": "%(ct)s", "filter":"%(filter)s"}]' % {
                                                'rtype':  self.rtype01.id,
                                                'ct':     ContentType.objects.get_for_model(Contact).id,
                                                'filter': 3213213543,
                                            }
                                       )

    def test_ok(self):
        get_ct = ContentType.objects.get_for_model
        ct_contact = get_ct(Contact)
        ct_orga    = get_ct(Organisation)

        field = RelationSubfiltersConditionsField(model=Contact)
        conditions = field.clean('[{"rtype": "%(rtype01)s", "has": true,  "ctype": "%(ct_contact)s", "filter":"%(filter01)s"},'
                                 ' {"rtype": "%(rtype02)s", "has": false, "ctype": "%(ct_orga)s",    "filter":"%(filter02)s"}]' % {
                                        'rtype01':    self.rtype01.id,
                                        'rtype02':    self.rtype02.id,
                                        'ct_contact': ct_contact,
                                        'ct_orga':    ct_orga,
                                        'filter01':   self.sub_efilter01.id,
                                        'filter02':   self.sub_efilter02.id,
                                    }
                                )
        self.assertEqual(2, len(conditions))

        condition = conditions[0]
        self.assertEqual(EntityFilterCondition.EFC_RELATION_SUBFILTER,      condition.type)
        self.assertEqual(self.rtype01.id,                                   condition.name)
        self.assertEqual({'has': True, 'filter_id': self.sub_efilter01.id}, condition.decoded_value)

        condition = conditions[1]
        self.assertEqual(EntityFilterCondition.EFC_RELATION_SUBFILTER,       condition.type)
        self.assertEqual(self.rtype02.id,                                    condition.name)
        self.assertEqual({'has': False, 'filter_id': self.sub_efilter02.id}, condition.decoded_value)


class DateRangeFieldTestCase(FieldTestCase):
    def test_clean_empty_customized(self):
        field = DateRangeField()
        self.assertFieldValidationError(DateRangeField, 'customized_empty', field.clean, [u"", u"", u""])
        self.assertFieldValidationError(DateRangeField, 'customized_empty', field.clean, None)

    def test_start_before_end(self):
        field = DateRangeField()
        self.assertFieldValidationError(DateRangeField, 'customized_invalid', field.clean, [u"", u"2011-05-16", u"2011-05-15"])


class EntityFieldTestCase(FieldTestCase):
    def test_empty01(self):
        from creme_core.forms.fields import _EntityField #Not included in __all__
        field = _EntityField()
        self.assertFieldValidationError(_EntityField, 'required', field.clean, None)

    def test_properties(self):
        from creme_core.forms.fields import _EntityField #Not included in __all__
        field = _EntityField()
        field.model = Contact
        self.assertEqual(Contact, field.widget.model)

        field.o2m = True
        self.assertEqual(1, field.widget.o2m)

    def test_invalid_choice01(self):
        from creme_core.forms.fields import _EntityField #Not included in __all__
        field = _EntityField()
        self.assertFieldValidationError(_EntityField, 'invalid_choice', field.clean, [u''], message_args={"value":[u'']})

    def test_ok01(self):
        from creme_core.forms.fields import _EntityField #Not included in __all__
        field = _EntityField()
        self.assertEqual([1, 2], field.clean([u'1', u'2']))


class CremeEntityFieldTestCase(FieldTestCase):
    def test_empty01(self):
        field = CremeEntityField()
        self.assertFieldValidationError(CremeEntityField, 'required', field.clean, None)

    def test_empty02(self):
        field = CremeEntityField()
        self.assertFieldValidationError(CremeEntityField, 'required', field.clean, [])

    def test_invalid_choice01(self):
        field = CremeEntityField()
        self.assertFieldValidationError(CremeEntityField, 'invalid_choice', field.clean, [u''], message_args={"value":[u'']})

    def test_doesnotexist01(self):
        field = CremeEntityField()
        self.assertFieldValidationError(CremeEntityField, 'doesnotexist', field.clean, [u'2'], message_args={"value":[u'2']})

    def test_ok01(self):
        self.login()
        field = CremeEntityField()
        ce = CremeEntity.objects.create(user=self.user)
        self.assertEqual(ce, field.clean([ce.id]))

    def test_ok02(self):
        self.login()
        field = CremeEntityField(required=False)
        ce = CremeEntity.objects.create(user=self.user)
        self.assertEqual(None, field.clean([]))

    def test_ok03(self):
        self.login()
        field = CremeEntityField(required=False)
        ce = CremeEntity.objects.create(user=self.user)
        self.assertEqual(None, field.clean(None))

    def test_q_filter01(self):
        self.login()
        ce = CremeEntity.objects.create(user=self.user)
        field = CremeEntityField(q_filter={'~pk': ce.id})

        self.assertFieldValidationError(CremeEntityField, 'doesnotexist', field.clean, [ce.id], message_args={"value":[ce.id]})

    def test_q_filter02(self):
        self.login()
        ce = CremeEntity.objects.create(user=self.user)
        field = CremeEntityField()
        field.q_filter={'~pk': ce.id}

        self.assertFieldValidationError(CremeEntityField, 'doesnotexist', field.clean, [ce.id], message_args={"value":[ce.id]})


class MultiCremeEntityFieldTestCase(FieldTestCase):
    def test_empty01(self):
        field = MultiCremeEntityField()
        self.assertFieldValidationError(MultiCremeEntityField, 'required', field.clean, None)

    def test_empty02(self):
        field = MultiCremeEntityField()
        self.assertFieldValidationError(MultiCremeEntityField, 'required', field.clean, [])

    def test_invalid_choice01(self):
        field = MultiCremeEntityField()
        self.assertFieldValidationError(MultiCremeEntityField, 'invalid_choice', field.clean, [u''], message_args={"value":[u'']})

    def test_invalid_choice02(self):
        field = MultiCremeEntityField()
        self.assertFieldValidationError(MultiCremeEntityField, 'invalid_choice', field.clean, [u'2', u'3'], message_args={"value":'2, 3'})

    def test_ok01(self):
        self.login()
        field = MultiCremeEntityField()
        ce1 = CremeEntity.objects.create(user=self.user)
        ce2 = CremeEntity.objects.create(user=self.user)
        self.assertEqual(set([ce1, ce2]), set(field.clean([ce1.id, ce2.id])))

    def test_ok02(self):
        self.login()
        field = MultiCremeEntityField(required=False)
        self.assertEqual([], field.clean([]))

    def test_q_filter01(self):
        self.login()
        ce1 = CremeEntity.objects.create(user=self.user)
        ce2 = CremeEntity.objects.create(user=self.user)
        field = MultiCremeEntityField(q_filter={'~pk__in': [ce1.id, ce2.id]})

        self.assertFieldValidationError(MultiCremeEntityField, 'invalid_choice', field.clean, [ce1.id, ce2.id], message_args={"value":'%s, %s' % (ce1.id, ce2.id)})

    def test_q_filter02(self):
        self.login()
        ce1 = CremeEntity.objects.create(user=self.user)
        ce2 = CremeEntity.objects.create(user=self.user)
        field = MultiCremeEntityField()
        field.q_filter={'~pk__in': [ce1.id, ce2.id]}

        self.assertFieldValidationError(MultiCremeEntityField, 'invalid_choice', field.clean, [ce1.id, ce2.id], message_args={"value":'%s, %s' % (ce1.id, ce2.id)})

class ColorFieldTestCase(FieldTestCase):
    def test_empty01(self):
        field = ColorField()
        self.assertFieldValidationError(ColorField, 'required', field.clean, None)
        self.assertFieldValidationError(ColorField, 'required', field.clean, '')
        self.assertFieldValidationError(ColorField, 'required', field.clean, [])

    def test_length01(self):
        field = ColorField()
        self.assertFieldRaises(ValidationError, field.clean, '1')
        self.assertFieldRaises(ValidationError, field.clean, '12')
        self.assertFieldRaises(ValidationError, field.clean, '123')
        self.assertFieldRaises(ValidationError, field.clean, '1234')
        self.assertFieldRaises(ValidationError, field.clean, '12345')

    def test_invalid_value01(self):
        field = ColorField()
        self.assertFieldValidationError(ColorField, 'invalid', field.clean, 'GGGGGG')
        self.assertFieldValidationError(ColorField, 'invalid', field.clean, '------')

    def test_ok01(self):
        field = ColorField()
        self.assertEqual('AAAAAA', field.clean('AAAAAA'))
        self.assertEqual('AAAAAA', field.clean('aaaaaa'))
        self.assertEqual('123456', field.clean('123456'))
        self.assertEqual('123ABC', field.clean('123ABC'))
        self.assertEqual('123ABC', field.clean('123abc'))


class DurationFieldTestCase(FieldTestCase):
    def test_empty01(self):
        field = DurationField()
        self.assertFieldValidationError(DurationField, 'required', field.clean, None)
        self.assertFieldValidationError(DurationField, 'required', field.clean, '')
        self.assertFieldValidationError(DurationField, 'required', field.clean, [])

    def test_invalid01(self):
        field = DurationField()
        self.assertFieldValidationError(DurationField, 'invalid', field.clean, [u'a', u'b', u'c'])

    def test_positive01(self):
        field = DurationField()
        self.assertFieldValidationError(DurationField, 'min_value', field.clean, [u'-1', u'-1', u'-1'], message_args={'limit_value': 0})

    def test_ok01(self):
        field = DurationField()
        self.assertEqual('10:2:0', field.clean([u'10', u'2', u'0']))
        self.assertEqual('10:2:0', field.clean([10, 2, 0]))
