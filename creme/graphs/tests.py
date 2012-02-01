# -*- coding: utf-8 -*-

try:
    from django.contrib.auth.models import User
    from django.contrib.contenttypes.models import ContentType

    from creme_core.models import RelationType, UserRole
    from creme_core.tests.base import CremeTestCase

    from graphs.models import *
except Exception as e:
    print 'Error:', e


class GraphsTestCase(CremeTestCase):
    @classmethod
    def setUpClass(cls):
        cls.populate('creme_core', 'creme_config')
    #def setUp(self):
        #self.populate('creme_core', 'creme_config', )

    def login(self, is_superuser=True):
        super(GraphsTestCase, self).login(is_superuser, allowed_apps=['graphs'])

    def test_graph_create(self):
        self.login()

        url = '/graphs/graph/add'
        self.assertEqual(200, self.client.get(url).status_code)

        name = 'Graph01'
        response = self.client.post(url, follow=True,
                                    data={'user': self.user.id,
                                          'name': name,
                                         }
                                   )
        self.assertNoFormError(response)
        self.assertEqual(200, response.status_code)

        graphs = Graph.objects.all()
        self.assertEqual(1,    len(graphs))
        self.assertEqual(name, graphs[0].name)

    def test_graph_edit(self):
        self.login()

        name = 'Nodz-a-lapalooza'
        graph = Graph.objects.create(user=self.user, name=name)

        url = '/graphs/graph/edit/%s' % graph.id
        self.assertEqual(200, self.client.get(url).status_code)

        name += '_edited'
        response = self.client.post(url, follow=True,
                                    data={'user': self.user.id,
                                          'name': name,
                                         }
                                   )
        self.assertNoFormError(response)
        self.assertEqual(200,  response.status_code)
        self.assertEqual(name, self.refresh(graph).name)

    def test_listview(self):
        self.login()

        Graph.objects.create(user=self.user, name='Graph01')
        Graph.objects.create(user=self.user, name='Graph02')

        self.assertEqual(200, self.client.get('/graphs/graphs').status_code)

    def test_relation_types01(self):
        self.login()

        graph = Graph.objects.create(user=self.user, name='Graph01')
        self.assertEqual(0, graph.orbital_relation_types.count())

        url = '/graphs/graph/%s/relation_types/add' % graph.id
        self.assertEqual(200, self.client.get(url).status_code)

        rtype_create = RelationType.create
        rtype01, srtype01 = rtype_create(('test-subject_love', 'loves'), ('test-object_love', 'is loved to'))
        rtype02, srtype02 = rtype_create(('test-subject_hate', 'hates'), ('test-object_hate', 'is hated to'))
        rtypes_ids = [rtype01.id, rtype02.id]

        response = self.client.post(url, data={'relation_types': rtypes_ids})
        self.assertNoFormError(response)
        self.assertEqual(200, response.status_code)

        rtypes = graph.orbital_relation_types.all()
        self.assertEqual(2,               len(rtypes))
        self.assertEqual(set(rtypes_ids), set(rt.id for rt in rtypes))

        response = self.client.post('/graphs/graph/%s/relation_type/delete' % graph.id,
                                    data={'id': rtype01.id}
                                   )
        self.assertEqual(200,          response.status_code)
        self.assertEqual([rtype02.id], [rt.id for rt in graph.orbital_relation_types.all()])

    def test_relation_types02(self):
        self.login(is_superuser=False)

        graph = Graph.objects.create(user=self.other_user, name='Graph01')
        self.assertEqual(403, self.client.get('/graphs/graph/%s/relation_types/add' % graph.id).status_code)

        rtype, srtype = RelationType.create(('test-subject_love', 'loves'), ('test-object_love', 'is loved to'))
        graph.orbital_relation_types.add(rtype)
        self.assertEqual(403,  self.client.post('/graphs/graph/%s/relation_type/delete' % graph.id,
                                                data={'id': rtype.id}
                                               ).status_code
                        )

    def test_download01(self):
        self.login()

        graph = Graph.objects.create(user=self.other_user, name='Graph01')
        self.assertEqual(200, self.client.get('/graphs/graph/%s/png' % graph.id, follow=True).status_code)

        #TODO: improve

    #TODO: def test_root_nodes_/add/edit/delete
