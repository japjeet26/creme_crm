# Generated by Django 3.2 on 2021-05-04 12:09

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('creme_core', '0080_v2_2__global_search_customfields02'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchconfigitem',
            name='field_names',
        ),
    ]
