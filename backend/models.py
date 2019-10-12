# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class SampleUser(models.Model):
    email = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sample_user'


class TblAgent(models.Model):
    name = models.CharField(max_length=200)
    hostdomain = models.CharField(max_length=200)
    hostip = models.CharField(max_length=100)
    is_active = models.IntegerField()
    is_status = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'tbl_agent'


class TblAndroidVersion(models.Model):
    ver_name = models.CharField(max_length=200, blank=True, null=True)
    ver_code = models.CharField(max_length=200, blank=True, null=True)
    remark = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_android_version'


class TblCodeDetail(models.Model):
    group_code = models.CharField(primary_key=True, max_length=100)
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    memo = models.CharField(max_length=10000, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)
    delete_yn = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_code_detail'
        unique_together = (('group_code', 'code'),)


class TblCodeGroup(models.Model):
    code = models.CharField(primary_key=True, max_length=100)
    name = models.CharField(max_length=200)
    memo = models.CharField(max_length=10000, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)
    delete_yn = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_code_group'


class TblCompanyManage(models.Model):
    type = models.CharField(primary_key=True, max_length=10)
    en = models.TextField(blank=True, null=True)
    ko = models.TextField(blank=True, null=True)
    ja = models.TextField(blank=True, null=True)
    zh = models.TextField(blank=True, null=True)
    en_modify_date = models.DateTimeField(blank=True, null=True)
    ko_modify_date = models.DateTimeField(blank=True, null=True)
    ja_modify_date = models.DateTimeField(blank=True, null=True)
    zh_modify_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_company_manage'


class TblDownloadManage(models.Model):
    type = models.CharField(max_length=100)
    language = models.CharField(max_length=100)
    client_name = models.CharField(max_length=300, blank=True, null=True)
    image_name = models.CharField(max_length=300, blank=True, null=True)
    client_real_size = models.IntegerField(blank=True, null=True)
    client_save_size = models.CharField(max_length=300, blank=True, null=True)
    client_save_path = models.CharField(max_length=300, blank=True, null=True)
    client_modify_date = models.DateTimeField(blank=True, null=True)
    image_real_size = models.IntegerField(blank=True, null=True)
    image_save_size = models.CharField(max_length=300, blank=True, null=True)
    image_save_path = models.CharField(max_length=300, blank=True, null=True)
    image_modify_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_download_manage'


class TblFile(models.Model):
    gname = models.CharField(max_length=255, blank=True, null=True)
    gid = models.CharField(max_length=255, blank=True, null=True)
    real_name = models.CharField(max_length=255)
    save_name = models.CharField(max_length=255)
    ext = models.CharField(max_length=255)
    real_size = models.IntegerField()
    save_size = models.CharField(max_length=255)
    save_path = models.CharField(max_length=255)
    regist_id = models.CharField(max_length=255, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    delete_yn = models.CharField(max_length=10, blank=True, null=True)
    delete_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_file'


class TblMenuManage(models.Model):
    type = models.CharField(max_length=100)
    use_yn = models.CharField(max_length=10)
    modify_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_menu_manage'


class TblNotice(models.Model):
    title_en = models.CharField(max_length=255, blank=True, null=True)
    title_ko = models.CharField(max_length=255, blank=True, null=True)
    title_ja = models.CharField(max_length=255, blank=True, null=True)
    title_zh = models.CharField(max_length=255, blank=True, null=True)
    content_en = models.TextField(blank=True, null=True)
    content_ko = models.TextField(blank=True, null=True)
    content_ja = models.TextField(blank=True, null=True)
    content_zh = models.TextField(blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)
    delete_date = models.DateTimeField(blank=True, null=True)
    delete_yn = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_notice'


class TblPolicyManage(models.Model):
    type = models.CharField(primary_key=True, max_length=10)
    en = models.TextField(blank=True, null=True)
    ko = models.TextField(blank=True, null=True)
    ja = models.TextField(blank=True, null=True)
    zh = models.TextField(blank=True, null=True)
    en_modify_date = models.DateTimeField(blank=True, null=True)
    ko_modify_date = models.DateTimeField(blank=True, null=True)
    ja_modify_date = models.DateTimeField(blank=True, null=True)
    zh_modify_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_policy_manage'


class TblPrice(models.Model):
    type_session = models.CharField(max_length=100, blank=True, null=True)
    type_month = models.CharField(max_length=100, blank=True, null=True)
    item_price = models.CharField(max_length=100, blank=True, null=True)
    item_price_usd = models.CharField(max_length=100, blank=True, null=True)
    item_price_jpy = models.CharField(max_length=100, blank=True, null=True)
    item_price_cny = models.CharField(max_length=100, blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)
    modify_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_price'


class TblPriceHistory(models.Model):
    tid = models.CharField(max_length=255, blank=True, null=True)
    user_id = models.IntegerField()
    pgcode = models.CharField(max_length=255, blank=True, null=True)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    session = models.IntegerField(blank=True, null=True)
    month_type = models.IntegerField(blank=True, null=True)
    krw = models.CharField(max_length=100, blank=True, null=True)
    usd = models.CharField(max_length=100, blank=True, null=True)
    jpy = models.CharField(max_length=100, blank=True, null=True)
    cny = models.CharField(max_length=100, blank=True, null=True)
    taxfree_amount = models.IntegerField(blank=True, null=True)
    tax_amount = models.IntegerField(blank=True, null=True)
    autopay_flag = models.CharField(max_length=10, blank=True, null=True)
    billkey = models.CharField(max_length=255, blank=True, null=True)
    refund_yn = models.CharField(max_length=10, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    refund_date = models.DateTimeField(blank=True, null=True)
    auto_end_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_price_history'


class TblReview(models.Model):
    language = models.CharField(max_length=10)
    star = models.IntegerField()
    content = models.CharField(max_length=1000)
    username = models.CharField(max_length=200)
    regist_date = models.DateTimeField(blank=True, null=True)
    regist_id = models.IntegerField(blank=True, null=True)
    modify_date = models.DateTimeField(blank=True, null=True)
    modify_id = models.IntegerField(blank=True, null=True)
    delete_yn = models.CharField(max_length=10, blank=True, null=True)
    delete_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_review'


class TblSupport(models.Model):
    email = models.CharField(max_length=255, blank=True, null=True)
    main_type = models.CharField(max_length=30, blank=True, null=True)
    sub_type = models.CharField(max_length=10, blank=True, null=True)
    title = models.CharField(max_length=1000, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    regist_ip = models.CharField(max_length=255, blank=True, null=True)
    regist_date = models.DateTimeField(blank=True, null=True)
    view_date = models.DateTimeField(blank=True, null=True)
    send_title = models.CharField(max_length=100, blank=True, null=True)
    send_content = models.TextField(blank=True, null=True)
    send_yn = models.CharField(max_length=10, blank=True, null=True)
    send_date = models.DateTimeField(blank=True, null=True)
    delete_yn = models.CharField(max_length=10, blank=True, null=True)
    delete_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_support'


class TblUser(models.Model):
    email = models.CharField(unique=True, max_length=100)
    password = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    phone = models.CharField(max_length=100)
    phone_country = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, blank=True, null=True)
    birth_date = models.CharField(max_length=8, blank=True, null=True)
    sns_code = models.CharField(max_length=100, blank=True, null=True)
    sns_name = models.CharField(max_length=100, blank=True, null=True)
    rec = models.CharField(max_length=100, blank=True, null=True)
    regist_rec = models.CharField(max_length=100, blank=True, null=True)
    regist_ip = models.CharField(max_length=100, blank=True, null=True)
    regist_date = models.DateTimeField()
    modify_date = models.DateTimeField(blank=True, null=True)
    is_active = models.IntegerField(blank=True, null=True)
    is_staff = models.IntegerField(blank=True, null=True)
    delete_yn = models.CharField(max_length=1, blank=True, null=True)
    black_yn = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_user'


class TblUserLogin(models.Model):
    user_id = models.IntegerField(unique=True)
    attempt = models.IntegerField(blank=True, null=True)
    login_ip = models.CharField(max_length=100, blank=True, null=True)
    login_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_user_login'


class TblWindowsVersion(models.Model):
    ver_code = models.CharField(max_length=200, blank=True, null=True)
    remark = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tbl_windows_version'
