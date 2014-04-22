import json
import logging
import os

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from celeryutils import task
from test_utils import RequestFactory

from amo.utils import chunked, JSONEncoder
from mkt.collections.models import Collection
from mkt.collections.serializers import CollectionSerializer
from mkt.constants.regions import RESTOFWORLD

task_log = logging.getLogger('collections.tasks')


def collection_filepath(collection):
    return os.path.join(settings.DUMPED_APPS_PATH,
                        'collections',
                        str(collection.pk / 1000),
                        '{pk}.json'.format(pk=collection.pk))


def collection_data(collection):
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    request.REGION = RESTOFWORLD
    return CollectionSerializer(collection, context={'request': request}).data


def write_file(filepath, output):
    target_path = os.path.dirname(filepath)
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    with open(filepath, 'w') as f:
        f.write(output)
    return filepath


def dump_collection(collection):
    target_file = collection_filepath(collection)
    task_log.info('Dumping collection {0} to {1}'.format(collection.pk,
                                                         target_file))
    json_collection = json.dumps(collection_data(collection),
                                 cls=JSONEncoder)
    return write_file(target_file, json_collection)


@task(ignore_result=False)
def dump_collections(pks):
    return [dump_collection(collection)
            for collection in Collection.public.filter(pk__in=pks).iterator()]


def dump_all_collections_tasks():
    all_pks = Collection.public.values_list('pk', flat=True).order_by('pk')
    return [dump_collections.si(pks) for pks in chunked(all_pks, 100)]
