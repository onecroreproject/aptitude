# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='customuser',
            old_name='profile_photo',
            new_name='profile_image',
        ),
        migrations.AlterField(
            model_name='customuser',
            name='profile_image',
            field=models.ImageField(blank=True, help_text='User profile picture.', null=True, upload_to='profile_images/'),
        ),
    ]
