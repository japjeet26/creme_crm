# Generated by Django 3.1.6 on 2021-02-11 16:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projecttask',
            name='order',
            field=models.PositiveIntegerField(default=1, editable=False, verbose_name='Order'),
            preserve_default=False,
        ),
    ]