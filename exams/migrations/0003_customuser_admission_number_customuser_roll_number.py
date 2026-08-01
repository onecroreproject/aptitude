# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0002_rename_profile_photo_customuser_profile_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='admission_number',
            field=models.CharField(blank=True, help_text='Unique admission number.', max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='roll_number',
            field=models.CharField(blank=True, help_text='Unique roll number.', max_length=30, null=True, unique=True),
        ),
    ]
