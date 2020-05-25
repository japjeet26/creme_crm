# -*- coding: utf-8 -*-

try:
    from django.contrib.contenttypes.models import ContentType
    from django.http import Http404

    from ..base import CremeTestCase

    from creme.creme_core.utils.content_type import (
        as_ctype,
        entity_ctypes,
        get_ctype_or_404,
        ctype_choices,
    )
    from creme.creme_core.models import (
        FakeOrganisation,
        FakeContact,
        FakeSector,
    )
except Exception as e:
    print(f'Error in <{__name__}>: {e}')


class ContentTypeTestCase(CremeTestCase):
    def test_as_ctype(self):
        ctype = ContentType.objects.get_for_model(FakeOrganisation)
        self.assertIs(ctype, as_ctype(ctype))
        self.assertEqual(ctype, as_ctype(FakeOrganisation))
        self.assertEqual(ctype, as_ctype(FakeOrganisation()))

    def test_creme_entity_content_types(self):
        ctypes = [*entity_ctypes()]

        get_ct = ContentType.objects.get_for_model
        self.assertIn(get_ct(FakeOrganisation), ctypes)
        self.assertIn(get_ct(FakeContact),      ctypes)

        self.assertNotIn(get_ct(FakeSector), ctypes)

        # DEPRECATED:
        from creme.creme_core import utils
        self.assertListEqual(ctypes, [*utils.creme_entity_content_types()])

    def test_get_ctype_or_404(self):
        get_ct = ContentType.objects.get_for_model
        ctype1 = get_ct(FakeOrganisation)

        with self.assertNoException():
            ct1 = get_ctype_or_404(ctype1.id)

        self.assertIsInstance(ct1, ContentType)
        self.assertEqual(FakeOrganisation, ct1.model_class())

        # Other model, str ----
        ctype2 = get_ct(FakeContact)

        with self.assertNoException():
            ct2 = get_ctype_or_404(str(ctype2.id))

        self.assertEqual(ctype2, ct2)

        # Errors ----
        with self.assertRaises(Http404):
            __ = get_ctype_or_404(1024)

        with self.assertRaises(Http404):
            __ = get_ctype_or_404('invalid')

        # DEPRECATED:
        from creme.creme_core import utils
        with self.assertNoException():
            ct2_depr = utils.get_ct_or_404(ctype2.id)
        self.assertEqual(ct2, ct2_depr)

    def test_ctype_choices(self):
        get_ct = ContentType.objects.get_for_model
        ctype1 = get_ct(FakeOrganisation)
        ctype2 = get_ct(FakeContact)

        choices = ctype_choices([ctype1, ctype2])
        self.assertIsInstance(choices, list)
        self.assertEqual(2, len(choices))
        self.assertInChoices(
            value=ctype1.id,
            label=FakeOrganisation._meta.verbose_name,
            choices=choices,
        )
        self.assertInChoices(
            value=ctype2.id,
            label=FakeContact._meta.verbose_name,
            choices=choices,
        )

        # DEPRECATED:
        from creme.creme_core import utils
        with self.assertNoException():
            choices_depr = utils.build_ct_choices([ctype1, ctype2])
        self.assertEqual(choices, choices_depr)