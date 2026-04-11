from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer as BaseTokenObtainPairSerializer,
)
from .models import (
    UserApproval,
    ensure_user_approval_record,
    ensure_user_profile,
    get_user_approval_record,
    get_user_approval_status,
    get_user_profile,
)

# 权限名称翻译映射
# 您可以根据实际的权限名称进行扩展
PERMISSION_NAME_TRANSLATIONS = {
    # 系统管理权限
    "Can add log entry": "添加日志条目",
    "Can change log entry": "修改日志条目",
    "Can delete log entry": "删除日志条目",
    "Can view log entry": "查看日志条目",
    # 用户认证权限
    "Can add group": "添加用户组",
    "Can add permission": "添加权限",
    "Can add user": "添加用户",
    "Can change group": "修改用户组",
    "Can change permission": "修改权限",
    "Can change user": "修改用户",
    "Can delete group": "删除用户组",
    "Can delete permission": "删除权限",
    "Can delete user": "删除用户",
    "Can view group": "查看用户组",
    "Can view permission": "查看权限",
    "Can view user": "查看用户",
    # 令牌权限
    "Can add Token": "添加令牌",
    "Can change Token": "修改令牌",
    "Can delete Token": "删除令牌",
    "Can view Token": "查看令牌",
    # 内容类型权限
    "Can add content type": "添加内容类型",
    "Can change content type": "修改内容类型",
    "Can delete content type": "删除内容类型",
    "Can view content type": "查看内容类型",
    # 会话权限
    "Can add session": "添加会话",
    "Can change session": "修改会话",
    "Can delete session": "删除会话",
    "Can view session": "查看会话",
    # 项目管理模块权限
    "Can add 项目": "添加项目",
    "Can change 项目": "修改项目",
    "Can delete 项目": "删除项目",
    "Can view 项目": "查看项目",
    "Can add 项目成员": "添加项目成员",
    "Can change 项目成员": "修改项目成员",
    "Can delete 项目成员": "删除项目成员",
    "Can view 项目成员": "查看项目成员",
    # 用例管理权限
    "Can add 测试用例": "添加测试用例",
    "Can change 测试用例": "修改测试用例",
    "Can delete 测试用例": "删除测试用例",
    "Can view 测试用例": "查看测试用例",
    "Can add 测试用例步骤": "添加测试用例步骤",
    "Can change 测试用例步骤": "修改测试用例步骤",
    "Can delete 测试用例步骤": "删除测试用例步骤",
    "Can view 测试用例步骤": "查看测试用例步骤",
    # LLM配置权限
    "Can add LLM Configuration": "添加LLM配置",
    "Can change LLM Configuration": "修改LLM配置",
    "Can delete LLM Configuration": "删除LLM配置",
    "Can view LLM Configuration": "查看LLM配置",
    # 对话会话权限
    "Can add 对话会话": "添加对话会话",
    "Can change 对话会话": "修改对话会话",
    "Can delete 对话会话": "删除对话会话",
    "Can view 对话会话": "查看对话会话",
    # 对话消息权限
    "Can add 对话消息": "添加对话消息",
    "Can change 对话消息": "修改对话消息",
    "Can delete 对话消息": "删除对话消息",
    "Can view 对话消息": "查看对话消息",
    # API密钥权限
    "Can add API Key": "添加API密钥",
    "Can change API Key": "修改API密钥",
    "Can delete API Key": "删除API密钥",
    "Can view API Key": "查看API密钥",
    # 知识库权限
    "Can add 知识库": "添加知识库",
    "Can change 知识库": "修改知识库",
    "Can delete 知识库": "删除知识库",
    "Can view 知识库": "查看知识库",
    "Can add 文档": "添加文档",
    "Can change 文档": "修改文档",
    "Can delete 文档": "删除文档",
    "Can view 文档": "查看文档",
    "Can add 知识库文档": "添加知识库文档",
    "Can change 知识库文档": "修改知识库文档",
    "Can delete 知识库文档": "删除知识库文档",
    "Can view 知识库文档": "查看知识库文档",
    # 需求管理权限
    "Can add 需求文档": "添加需求文档",
    "Can change 需求文档": "修改需求文档",
    "Can delete 需求文档": "删除需求文档",
    "Can view 需求文档": "查看需求文档",
    "Can add 需求模块": "添加需求模块",
    "Can change 需求模块": "修改需求模块",
    "Can delete 需求模块": "删除需求模块",
    "Can view 需求模块": "查看需求模块",
    "Can add 评审报告": "添加评审报告",
    "Can change 评审报告": "修改评审报告",
    "Can delete 评审报告": "删除评审报告",
    "Can view 评审报告": "查看评审报告",
    "Can add 评审问题": "添加评审问题",
    "Can change 评审问题": "修改评审问题",
    "Can delete 评审问题": "删除评审问题",
    "Can view 评审问题": "查看评审问题",
    "Can add 模块评审结果": "添加模块评审结果",
    "Can change 模块评审结果": "修改模块评审结果",
    "Can delete 模块评审结果": "删除模块评审结果",
    "Can view 模块评审结果": "查看模块评审结果",
    # 提示词管理权限
    "Can add 用户提示词": "添加用户提示词",
    "Can change 用户提示词": "修改用户提示词",
    "Can delete 用户提示词": "删除用户提示词",
    "Can view 用户提示词": "查看用户提示词",
    # MCP工具权限
    "Can add 远程 MCP 配置": "添加远程MCP配置",
    "Can change 远程 MCP 配置": "修改远程MCP配置",
    "Can delete 远程 MCP 配置": "删除远程MCP配置",
    "Can view 远程 MCP 配置": "查看远程MCP配置",
    # 知识库扩展权限
    "Can add 文档分块": "添加文档分块",
    "Can change 文档分块": "修改文档分块",
    "Can delete 文档分块": "删除文档分块",
    "Can view 文档分块": "查看文档分块",
    "Can add 查询日志": "添加查询日志",
    "Can change 查询日志": "修改查询日志",
    "Can delete 查询日志": "删除查询日志",
    "Can view 查询日志": "查看查询日志",
    # LLM配置相关权限
    "Can add LLM配置": "添加LLM配置",
    "Can change LLM配置": "修改LLM配置",
    "Can delete LLM配置": "删除LLM配置",
    "Can view LLM配置": "查看LLM配置",
    "Can add LLM模型": "添加LLM模型",
    "Can change LLM模型": "修改LLM模型",
    "Can delete LLM模型": "删除LLM模型",
    "Can view LLM模型": "查看LLM模型",
    # LLM服务相关权限
    "Can add LLM服务": "添加LLM服务",
    "Can change LLM服务": "修改LLM服务",
    "Can delete LLM服务": "删除LLM服务",
    "Can view LLM服务": "查看LLM服务",
    # LLM提供商相关权限
    "Can add LLM提供商": "添加LLM提供商",
    "Can change LLM提供商": "修改LLM提供商",
    "Can delete LLM提供商": "删除LLM提供商",
    "Can view LLM提供商": "查看LLM提供商",
    # API密钥/秘钥相关权限
    "Can add 密钥": "添加密钥",
    "Can change 密钥": "修改密钥",
    "Can delete 密钥": "删除密钥",
    "Can view 密钥": "查看密钥",
    "Can add 秘钥": "添加秘钥",
    "Can change 秘钥": "修改秘钥",
    "Can delete 秘钥": "删除秘钥",
    "Can view 秘钥": "查看秘钥",
    # 用例管理相关权限
    "Can add 用例": "添加用例",
    "Can change 用例": "修改用例",
    "Can delete 用例": "删除用例",
    "Can view 用例": "查看用例",
    "Can add 用例步骤": "添加用例步骤",
    "Can change 用例步骤": "修改用例步骤",
    "Can delete 用例步骤": "删除用例步骤",
    "Can view 用例步骤": "查看用例步骤",
    "Can add 用例执行记录": "添加用例执行记录",
    "Can change 用例执行记录": "修改用例执行记录",
    "Can delete 用例执行记录": "删除用例执行记录",
    "Can view 用例执行记录": "查看用例执行记录",
    "Can add 用例模块": "添加用例模块",
    "Can change 用例模块": "修改用例模块",
    "Can delete 用例模块": "删除用例模块",
    "Can view 用例模块": "查看用例模块",
    "Can add 用例截屏": "添加用例截屏",
    "Can change 用例截屏": "修改用例截屏",
    "Can delete 用例截屏": "删除用例截屏",
    "Can view 用例截屏": "查看用例截屏",
    "Can add 测试用例截屏": "添加测试用例截屏",
    "Can change 测试用例截屏": "修改测试用例截屏",
    "Can delete 测试用例截屏": "删除测试用例截屏",
    "Can view 测试用例截屏": "查看测试用例截屏",
    # 消息相关权限
    "Can add 消息": "添加消息",
    "Can change 消息": "修改消息",
    "Can delete 消息": "删除消息",
    "Can view 消息": "查看消息",
    # MCP服务器配置权限
    "Can add MCP服务器配置": "添加MCP服务器配置",
    "Can change MCP服务器配置": "修改MCP服务器配置",
    "Can delete MCP服务器配置": "删除MCP服务器配置",
    "Can view MCP服务器配置": "查看MCP服务器配置",
    # API密钥相关权限
    "Can add API密钥": "添加API密钥",
    "Can change API密钥": "修改API密钥",
    "Can delete API密钥": "删除API密钥",
    "Can view API密钥": "查看API密钥",
    # 对话相关权限
    "Can add 对话": "添加对话",
    "Can change 对话": "修改对话",
    "Can delete 对话": "删除对话",
    "Can view 对话": "查看对话",
    # 向量数据库索引相关权限
    "Can add 向量数据库索引": "添加向量数据库索引",
    "Can change 向量数据库索引": "修改向量数据库索引",
    "Can delete 向量数据库索引": "删除向量数据库索引",
    "Can view 向量数据库索引": "查看向量数据库索引",
}


class UserApprovalMixin(serializers.Serializer):
    approval_status = serializers.SerializerMethodField()
    approval_status_display = serializers.SerializerMethodField()
    approval_review_note = serializers.SerializerMethodField()
    approval_reviewed_at = serializers.SerializerMethodField()
    approval_reviewed_by = serializers.SerializerMethodField()

    def get_approval_status(self, obj):
        return get_user_approval_status(obj)

    def get_approval_status_display(self, obj):
        status = get_user_approval_status(obj)
        return dict(UserApproval.STATUS_CHOICES).get(status, status)

    def get_approval_review_note(self, obj):
        approval = get_user_approval_record(obj)
        return approval.review_note if approval else ""

    def get_approval_reviewed_at(self, obj):
        approval = get_user_approval_record(obj)
        return approval.reviewed_at if approval else None

    def get_approval_reviewed_by(self, obj):
        approval = get_user_approval_record(obj)
        if approval and approval.reviewed_by:
            return approval.reviewed_by.username
        return None


class UserProfileMixin(serializers.Serializer):
    phone_number = serializers.SerializerMethodField()
    real_name = serializers.SerializerMethodField()

    def get_phone_number(self, obj):
        profile = get_user_profile(obj)
        return profile.phone_number if profile else ""

    def get_real_name(self, obj):
        profile = get_user_profile(obj)
        return profile.real_name if profile else ""


class UserSerializer(UserApprovalMixin, UserProfileMixin, serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "real_name",
            "is_staff",
            "is_active",
            "approval_status",
            "approval_status_display",
            "approval_review_note",
            "approval_reviewed_at",
            "approval_reviewed_by",
        )  # 添加管理员相关字段

    def create(self, validated_data):
        registration_mode = bool(self.context.get("registration_mode"))
        # 信号处理器会自动处理管理员权限分配，这里只需要正常创建用户
        # 统一走 create_user，确保密码会被哈希而不是明文入库。
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_staff=False if registration_mode else validated_data.get("is_staff", False),
            is_active=validated_data.get("is_active", True),
        )

        ensure_user_approval_record(
            user,
            status=UserApproval.STATUS_PENDING if registration_mode else UserApproval.STATUS_APPROVED,
        )
        profile = ensure_user_profile(user)
        profile.phone_number = validated_data.get("phone_number", "")
        profile.real_name = validated_data.get("real_name", "")
        profile.save(update_fields=["phone_number", "real_name", "updated_at"])

        return user


class UserDetailSerializer(UserApprovalMixin, UserProfileMixin, serializers.ModelSerializer):
    """
    用于展示用户详情（只读，不包含密码）。
    """

    groups = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "real_name",
            "is_staff",
            "is_active",
            "groups",
            "approval_status",
            "approval_status_display",
            "approval_review_note",
            "approval_reviewed_at",
            "approval_reviewed_by",
        )  # 根据需要添加更多字段
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    用于管理员更新用户信息。
    密码字段非必填，若传入则会单独处理。
    """

    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=30)
    real_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, required=False
    )
    # 可按需补充管理员可更新字段
    # 例如：first_name、last_name、is_staff、is_active

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "real_name",
            "is_staff",
            "is_active",
            "password",
            "groups",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": False,
                "style": {"input_type": "password"},
            },
            "username": {"required": False},
            "email": {"required": False},
            # groups 字段保持 PrimaryKeyRelatedField 默认行为
        }

    def update(self, instance, validated_data):
        # 信号处理器会自动处理管理员权限分配，这里只需要正常更新用户



        # 条件：请求携带新密码；动作：调用 set_password；结果：确保密码按 Django 标准安全存储。
        password = validated_data.pop("password", None)
        if password:
            instance.set_password(password)

        # 条件：请求包含 groups；动作：整体替换用户组；结果：组关系与请求保持一致。
        if "groups" in validated_data:
            instance.groups.set(validated_data.pop("groups"))

        profile = ensure_user_profile(instance)
        if "phone_number" in validated_data:
            profile.phone_number = validated_data.pop("phone_number")
        if "real_name" in validated_data:
            profile.real_name = validated_data.pop("real_name")
        profile.save(update_fields=["phone_number", "real_name", "updated_at"])

        # 其余字段逐项赋值，避免遗漏可编辑基础资料字段。
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()  # 保存时会触发信号处理器

        return instance


class GroupSerializer(serializers.ModelSerializer):
    users = serializers.StringRelatedField(many=True, read_only=True, source="user_set")

    class Meta:
        model = Group
        fields = ("id", "name", "users")


class ContentTypeSerializer(serializers.ModelSerializer):
    app_label_cn = serializers.SerializerMethodField()
    app_label_sort = serializers.SerializerMethodField()
    app_label_subcategory = serializers.SerializerMethodField()
    app_label_subcategory_sort = serializers.SerializerMethodField()
    model_cn = serializers.SerializerMethodField()
    model_sort = serializers.SerializerMethodField()
    model_verbose = serializers.SerializerMethodField()

    class Meta:
        model = ContentType
        fields = (
            "id",
            "app_label",
            "app_label_cn",
            "app_label_subcategory",
            "app_label_subcategory_sort",
            "app_label_sort",
            "model",
            "model_cn",
            "model_sort",
            "model_verbose",
        )

    MENU_CATEGORY_MAP = {
        "projects": "\u9879\u76ee\u7ba1\u7406",
        "requirements": "\u9700\u6c42\u7ba1\u7406",
        "testcases": "\u6d4b\u8bd5\u7ba1\u7406",
        "api_automation": "API\u81ea\u52a8\u5316",
        "app_automation": "APP\u81ea\u52a8\u5316",
        "ui_automation": "UI\u81ea\u52a8\u5316",
        "knowledge": "\u77e5\u8bc6\u5e93\u7ba1\u7406",
        "data_factory": "\u6570\u636e\u5de5\u5382",
        "auth": "\u7cfb\u7edf\u7ba1\u7406",
        "accounts": "\u7cfb\u7edf\u7ba1\u7406",
        "api_keys": "\u7cfb\u7edf\u7ba1\u7406",
        "mcp_tools": "\u7cfb\u7edf\u7ba1\u7406",
        "skills": "\u7cfb\u7edf\u7ba1\u7406",
    }

    MENU_SORT_ORDER = {
        "\u9879\u76ee\u7ba1\u7406": 1,
        "\u9700\u6c42\u7ba1\u7406": 2,
        "\u6d4b\u8bd5\u7ba1\u7406": 3,
        "API\u81ea\u52a8\u5316": 4,
        "APP\u81ea\u52a8\u5316": 5,
        "UI\u81ea\u52a8\u5316": 6,
        "AI \u5bf9\u8bdd": 7,
        "\u77e5\u8bc6\u5e93\u7ba1\u7406": 8,
        "\u6570\u636e\u5de5\u5382": 9,
        "\u7cfb\u7edf\u7ba1\u7406": 10,
    }

    SUBCATEGORY_SORT_ORDER = {
        "\u6d4b\u8bd5\u7528\u4f8b": 1,
        "\u8bf7\u6c42\u7ba1\u7406": 1,
        "\u9875\u9762\u7ba1\u7406": 1,
        "\u6982\u89c8": 1,
        "\u6d4b\u8bd5\u5957\u4ef6": 2,
        "\u9875\u9762\u6b65\u9aa4": 2,
        "\u8bbe\u5907\u7ba1\u7406": 2,
        "\u6267\u884c\u5386\u53f2": 3,
        "\u73af\u5883\u914d\u7f6e": 3,
        "\u5e94\u7528\u5305": 3,
        "\u6743\u9650\u7ba1\u7406": 3,
        "\u6267\u884c\u8bb0\u5f55": 4,
        "AI\u5927\u6a21\u578b\u914d\u7f6e": 4,
        "\u6d4b\u8bd5\u62a5\u544a": 5,
        "API KEY \u7ba1\u7406": 5,
        "\u5143\u7d20\u7ba1\u7406": 5,
        "MCP \u914d\u7f6e": 6,
        "\u573a\u666f\u7f16\u6392": 6,
        "\u516c\u5171\u6570\u636e": 7,
        "Skills \u7ba1\u7406": 7,
        "\u4f7f\u7528\u8bb0\u5f55": 1,
        "\u6807\u7b7e\u7ba1\u7406": 2,
        "\u5b9a\u65f6\u4efb\u52a1": 8,
        "\u6267\u884c\u5668": 9,
        "\u901a\u77e5\u65e5\u5fd7": 9,
        "\u6267\u884c\u62a5\u544a": 10,
        "\u73af\u5883\u8bbe\u7f6e": 11,
        "\u7ec4\u7ec7\u7ba1\u7406": 2,
        "\u7528\u6237\u7ba1\u7406": 1,
    }

    MODEL_NAME_MAP = {
        "projects.project": "\u9879\u76ee",
        "projects.projectmember": "\u9879\u76ee\u6210\u5458",
        "projects.projectcredential": "\u9879\u76ee\u51ed\u636e",
        "requirements.requirementdocument": "\u9700\u6c42\u6587\u6863",
        "requirements.requirementmodule": "\u9700\u6c42\u6a21\u5757",
        "requirements.reviewreport": "\u8bc4\u5ba1\u62a5\u544a",
        "requirements.reviewissue": "\u8bc4\u5ba1\u95ee\u9898",
        "requirements.modulereviewresult": "\u6a21\u5757\u8bc4\u5ba1\u7ed3\u679c",
        "requirements.documentimage": "\u6587\u6863\u56fe\u7247",
        "testcases.testcase": "\u6d4b\u8bd5\u7528\u4f8b",
        "testcases.testsuite": "\u6d4b\u8bd5\u5957\u4ef6",
        "testcases.testexecution": "\u6267\u884c\u5386\u53f2",
        "testcases.testcaseresult": "\u6267\u884c\u7ed3\u679c",
        "testcases.testcasemodule": "\u7528\u4f8b\u6a21\u5757",
        "testcases.testcasestep": "\u7528\u4f8b\u6b65\u9aa4",
        "testcases.testcasescreenshot": "\u7528\u4f8b\u622a\u56fe",
        "api_automation.apicollection": "\u63a5\u53e3\u76ee\u5f55",
        "api_automation.apirequest": "\u63a5\u53e3\u8bf7\u6c42",
        "api_automation.apirequestspec": "\u8bf7\u6c42\u89c4\u683c",
        "api_automation.apirequestfieldspec": "\u8bf7\u6c42\u5b57\u6bb5\u89c4\u5219",
        "api_automation.apirequestfilespec": "\u8bf7\u6c42\u6587\u4ef6\u89c4\u5219",
        "api_automation.apirequestauthspec": "\u8bf7\u6c42\u8ba4\u8bc1\u914d\u7f6e",
        "api_automation.apirequesttransportspec": "\u8bf7\u6c42\u4f20\u8f93\u914d\u7f6e",
        "api_automation.apiimportjob": "\u5bfc\u5165\u4efb\u52a1",
        "api_automation.apitestcase": "API\u6d4b\u8bd5\u7528\u4f8b",
        "api_automation.apitestcaseoverridespec": "\u7528\u4f8b\u8986\u76d6\u89c4\u5219",
        "api_automation.apitestcasefieldspec": "\u7528\u4f8b\u5b57\u6bb5\u89c4\u5219",
        "api_automation.apitestcasefilespec": "\u7528\u4f8b\u6587\u4ef6\u89c4\u5219",
        "api_automation.apitestcaseauthspec": "\u7528\u4f8b\u8ba4\u8bc1\u914d\u7f6e",
        "api_automation.apitestcasetransportspec": "\u7528\u4f8b\u4f20\u8f93\u914d\u7f6e",
        "api_automation.apiassertionspec": "\u65ad\u8a00\u89c4\u5219",
        "api_automation.apiextractorspec": "\u63d0\u53d6\u89c4\u5219",
        "api_automation.apicasegenerationjob": "\u7528\u4f8b\u751f\u6210\u4efb\u52a1",
        "api_automation.apienvironment": "API\u73af\u5883\u914d\u7f6e",
        "api_automation.apienvironmentvariablespec": "\u73af\u5883\u53d8\u91cf",
        "api_automation.apienvironmentheaderspec": "\u73af\u5883\u8bf7\u6c42\u5934",
        "api_automation.apienvironmentcookiespec": "\u73af\u5883 Cookie",
        "api_automation.apiexecutionrecord": "API\u6267\u884c\u8bb0\u5f55",
        "api_automation.apiexecutionreport": "API\u6d4b\u8bd5\u62a5\u544a",
        "ui_automation.uimodule": "\u9875\u9762\u6a21\u5757",
        "ui_automation.uipage": "UI\u9875\u9762",
        "ui_automation.uielement": "UI\u5143\u7d20",
        "ui_automation.uipagesteps": "\u9875\u9762\u6b65\u9aa4",
        "ui_automation.uipagestepsdetailed": "\u9875\u9762\u6b65\u9aa4\u660e\u7ec6",
        "ui_automation.uitestcase": "UI\u6d4b\u8bd5\u7528\u4f8b",
        "ui_automation.uicasestepsdetailed": "\u7528\u4f8b\u6b65\u9aa4\u660e\u7ec6",
        "ui_automation.uiexecutionrecord": "UI\u6267\u884c\u8bb0\u5f55",
        "ui_automation.uibatchexecutionrecord": "UI\u6279\u91cf\u6267\u884c\u8bb0\u5f55",
        "ui_automation.uiaicase": "AI\u667a\u80fd\u6a21\u5f0f",
        "ui_automation.uiaiexecutionrecord": "AI\u667a\u80fd\u6267\u884c\u8bb0\u5f55",
        "ui_automation.uipublicdata": "\u516c\u5171\u6570\u636e",
        "ui_automation.uienvironmentconfig": "UI\u73af\u5883\u914d\u7f6e",
        "ui_automation.uiactuator": "\u6267\u884c\u5668",
        "app_automation.appautomationoverview": "\u6982\u89c8",
        "app_automation.appautomationdevice": "\u8bbe\u5907\u7ba1\u7406",
        "app_automation.appautomationpackage": "\u5e94\u7528\u5305",
        "app_automation.appautomationelement": "\u5143\u7d20\u7ba1\u7406",
        "app_automation.appautomationscenebuilder": "\u573a\u666f\u7f16\u6392",
        "app_automation.appautomationtestcase": "\u6d4b\u8bd5\u7528\u4f8b",
        "app_automation.appautomationsuite": "\u6d4b\u8bd5\u5957\u4ef6",
        "app_automation.appautomationexecution": "\u6267\u884c\u8bb0\u5f55",
        "app_automation.appautomationscheduledtask": "\u5b9a\u65f6\u4efb\u52a1",
        "app_automation.appautomationnotification": "\u901a\u77e5\u65e5\u5fd7",
        "app_automation.appautomationreport": "\u6267\u884c\u62a5\u544a",
        "app_automation.appautomationsettings": "\u73af\u5883\u8bbe\u7f6e",
        "knowledge.knowledgebase": "\u77e5\u8bc6\u5e93",
        "knowledge.document": "\u6587\u6863",
        "knowledge.documentchunk": "\u6587\u6863\u5206\u5757",
        "knowledge.querylog": "\u67e5\u8be2\u65e5\u5fd7",
        "knowledge.knowledgeglobalconfig": "\u77e5\u8bc6\u5e93\u5168\u5c40\u914d\u7f6e",
        "langgraph_integration.llmconfig": "AI\u5927\u6a21\u578b\u914d\u7f6e",
        "langgraph_integration.chatsession": "\u5bf9\u8bdd\u4f1a\u8bdd",
        "langgraph_integration.chatmessage": "\u5bf9\u8bdd\u6d88\u606f",
        "langgraph_integration.usertoolapproval": "\u5de5\u5177\u5ba1\u6279\u504f\u597d",
        "prompts.userprompt": "\u63d0\u793a\u8bcd",
        "api_keys.apikey": "API KEY",
        "mcp_tools.remotemcpconfig": "MCP \u914d\u7f6e",
        "mcp_tools.mcptool": "MCP \u5de5\u5177",
        "skills.skill": "Skills",
        "auth.user": "\u7528\u6237",
        "auth.group": "\u7ec4\u7ec7",
        "auth.permission": "\u6743\u9650",
    }

    MODEL_SORT_ORDER = {
        "projects.project": 1,
        "projects.projectmember": 2,
        "projects.projectcredential": 3,
        "requirements.requirementdocument": 1,
        "requirements.requirementmodule": 2,
        "requirements.reviewreport": 3,
        "requirements.reviewissue": 4,
        "requirements.modulereviewresult": 5,
        "requirements.documentimage": 6,
        "testcases.testcase": 1,
        "testcases.testcasemodule": 2,
        "testcases.testcasestep": 3,
        "testcases.testcasescreenshot": 4,
        "testcases.testsuite": 5,
        "testcases.testexecution": 6,
        "testcases.testcaseresult": 7,
        "api_automation.apicollection": 1,
        "api_automation.apirequest": 2,
        "api_automation.apirequestspec": 3,
        "api_automation.apirequestfieldspec": 4,
        "api_automation.apirequestfilespec": 5,
        "api_automation.apirequestauthspec": 6,
        "api_automation.apirequesttransportspec": 7,
        "api_automation.apiimportjob": 8,
        "api_automation.apitestcase": 1,
        "api_automation.apitestcaseoverridespec": 2,
        "api_automation.apitestcasefieldspec": 3,
        "api_automation.apitestcasefilespec": 4,
        "api_automation.apitestcaseauthspec": 5,
        "api_automation.apitestcasetransportspec": 6,
        "api_automation.apiassertionspec": 7,
        "api_automation.apiextractorspec": 8,
        "api_automation.apicasegenerationjob": 9,
        "api_automation.apienvironment": 1,
        "api_automation.apienvironmentvariablespec": 2,
        "api_automation.apienvironmentheaderspec": 3,
        "api_automation.apienvironmentcookiespec": 4,
        "api_automation.apiexecutionrecord": 1,
        "api_automation.apiexecutionreport": 1,
        "app_automation.appautomationoverview": 1,
        "app_automation.appautomationdevice": 2,
        "app_automation.appautomationpackage": 3,
        "app_automation.appautomationelement": 4,
        "app_automation.appautomationscenebuilder": 5,
        "app_automation.appautomationtestcase": 6,
        "app_automation.appautomationsuite": 7,
        "app_automation.appautomationexecution": 8,
        "app_automation.appautomationscheduledtask": 9,
        "app_automation.appautomationnotification": 10,
        "app_automation.appautomationreport": 11,
        "app_automation.appautomationsettings": 12,
        "ui_automation.uimodule": 1,
        "ui_automation.uipage": 2,
        "ui_automation.uielement": 3,
        "ui_automation.uipagesteps": 1,
        "ui_automation.uipagestepsdetailed": 2,
        "ui_automation.uitestcase": 1,
        "ui_automation.uicasestepsdetailed": 2,
        "ui_automation.uiaicase": 1,
        "ui_automation.uiaiexecutionrecord": 2,
        "ui_automation.uiexecutionrecord": 1,
        "ui_automation.uibatchexecutionrecord": 1,
        "ui_automation.uipublicdata": 1,
        "ui_automation.uienvironmentconfig": 1,
        "ui_automation.uiactuator": 1,
        "data_factory.datafactoryrecord": 1,
        "data_factory.datafactorytag": 2,
        "knowledge.knowledgebase": 1,
        "knowledge.document": 2,
        "knowledge.documentchunk": 3,
        "knowledge.querylog": 4,
        "knowledge.knowledgeglobalconfig": 5,
        "langgraph_integration.chatsession": 1,
        "langgraph_integration.chatmessage": 2,
        "langgraph_integration.usertoolapproval": 3,
        "langgraph_integration.llmconfig": 1,
        "prompts.userprompt": 4,
        "api_keys.apikey": 1,
        "mcp_tools.remotemcpconfig": 1,
        "mcp_tools.mcptool": 2,
        "skills.skill": 1,
        "auth.user": 1,
        "auth.group": 2,
        "auth.permission": 3,
    }

    def get_app_label_cn(self, obj):
        app_label = obj.app_label
        model_name = (obj.model or "").lower()
        if app_label == "langgraph_integration":
            if model_name == "llmconfig":
                return "\u7cfb\u7edf\u7ba1\u7406"
            if model_name in ["chatsession", "chatmessage", "usertoolapproval"]:
                return "AI \u5bf9\u8bdd"
        if app_label == "prompts":
            return "AI \u5bf9\u8bdd"
        return self.MENU_CATEGORY_MAP.get(app_label, "\u7cfb\u7edf\u7ba1\u7406")

    def get_app_label_subcategory(self, obj):
        menu_category = self.get_app_label_cn(obj)
        app_label = obj.app_label
        model_name = (obj.model or "").lower()

        if menu_category == "\u6d4b\u8bd5\u7ba1\u7406" and app_label == "testcases":
            if model_name == "testsuite":
                return "\u6d4b\u8bd5\u5957\u4ef6"
            if model_name in ["testexecution", "testcaseresult"]:
                return "\u6267\u884c\u5386\u53f2"
            return "\u6d4b\u8bd5\u7528\u4f8b"

        if menu_category == "API\u81ea\u52a8\u5316":
            if model_name in [
                "apicollection", "apirequest", "apirequestspec", "apirequestfieldspec",
                "apirequestfilespec", "apirequestauthspec", "apirequesttransportspec", "apiimportjob"
            ]:
                return "\u8bf7\u6c42\u7ba1\u7406"
            if model_name in [
                "apitestcase", "apitestcaseoverridespec", "apitestcasefieldspec", "apitestcasefilespec",
                "apitestcaseauthspec", "apitestcasetransportspec", "apiassertionspec", "apiextractorspec",
                "apicasegenerationjob"
            ]:
                return "\u6d4b\u8bd5\u7528\u4f8b"
            if model_name in [
                "apienvironment", "apienvironmentvariablespec", "apienvironmentheaderspec", "apienvironmentcookiespec"
            ]:
                return "\u73af\u5883\u914d\u7f6e"
            if model_name == "apiexecutionrecord":
                return "\u6267\u884c\u8bb0\u5f55"
            if model_name == "apiexecutionreport":
                return "\u6d4b\u8bd5\u62a5\u544a"
            return None

        if menu_category == "UI\u81ea\u52a8\u5316":
            if model_name in ["uimodule", "uipage", "uielement"]:
                return "\u9875\u9762\u7ba1\u7406"
            if model_name in ["uipagesteps", "uipagestepsdetailed"]:
                return "\u9875\u9762\u6b65\u9aa4"
            if model_name in ["uitestcase", "uicasestepsdetailed"]:
                return "\u6d4b\u8bd5\u7528\u4f8b"
            if model_name in ["uiaicase", "uiaiexecutionrecord"]:
                return "AI\u667a\u80fd\u6a21\u5f0f"
            if model_name == "uiexecutionrecord":
                return "\u6267\u884c\u8bb0\u5f55"
            if model_name == "uibatchexecutionrecord":
                return "\u6279\u91cf\u6267\u884c"
            if model_name == "uipublicdata":
                return "\u516c\u5171\u6570\u636e"
            if model_name == "uienvironmentconfig":
                return "\u73af\u5883\u914d\u7f6e"
            if model_name == "uiactuator":
                return "\u6267\u884c\u5668"
            return None

        if menu_category == "\u6570\u636e\u5de5\u5382":
            if model_name == "datafactoryrecord":
                return "\u4f7f\u7528\u8bb0\u5f55"
            if model_name == "datafactorytag":
                return "\u6807\u7b7e\u7ba1\u7406"
            return None

        if menu_category == "\u7cfb\u7edf\u7ba1\u7406":
            if app_label == "langgraph_integration" and model_name == "llmconfig":
                return "AI\u5927\u6a21\u578b\u914d\u7f6e"
            if app_label == "auth":
                return self._get_auth_subcategory(obj)
            return {
                "accounts": "\u6743\u9650\u7ba1\u7406",
                "api_keys": "API KEY \u7ba1\u7406",
                "mcp_tools": "MCP \u914d\u7f6e",
                "skills": "Skills \u7ba1\u7406",
            }.get(app_label)

        return None

    def _get_auth_subcategory(self, obj):
        model_name = (obj.model or "").lower()
        if model_name == "user":
            return "\u7528\u6237\u7ba1\u7406"
        if model_name == "group":
            return "\u7ec4\u7ec7\u7ba1\u7406"
        if model_name == "permission":
            return "\u6743\u9650\u7ba1\u7406"
        return None

    def get_app_label_subcategory_sort(self, obj):
        subcategory = self.get_app_label_subcategory(obj)
        if not subcategory:
            return 99
        return self.SUBCATEGORY_SORT_ORDER.get(subcategory, 99)

    def get_app_label_sort(self, obj):
        return self.MENU_SORT_ORDER.get(self.get_app_label_cn(obj), 99)

    def get_model_cn(self, obj):
        app_model_key = f"{obj.app_label}.{obj.model}"
        if app_model_key in self.MODEL_NAME_MAP:
            return self.MODEL_NAME_MAP[app_model_key]
        try:
            verbose_name = obj.model_class()._meta.verbose_name
            return str(verbose_name)
        except Exception:
            return obj.model

    def get_model_verbose(self, obj):
        return self.get_model_cn(obj)

    def get_model_sort(self, obj):
        app_model_key = f"{obj.app_label}.{obj.model}"
        return self.MODEL_SORT_ORDER.get(app_model_key, 99)


class PermissionSerializer(serializers.ModelSerializer):
    content_type = ContentTypeSerializer(
        read_only=True
    )  # 使用嵌套的ContentTypeSerializer
    name_cn = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ("id", "name", "name_cn", "codename", "content_type")

    def get_name_cn(self, obj):
        """
        返回权限名称的中文翻译。
        """
        # 优先从 PERMISSION_NAME_TRANSLATIONS 映射中获取
        # 如果Django的i18n配置好了，也可以直接翻译obj.name
        # 例如: return _(obj.name)
        translated_name = PERMISSION_NAME_TRANSLATIONS.get(obj.name)
        if translated_name:
            return translated_name

        # 对未显式配置的标准CRUD权限，基于 codename 动态生成中文名称
        action_map = {
            "add": "添加",
            "change": "修改",
            "delete": "删除",
            "view": "查看",
        }
        codename = getattr(obj, "codename", "") or ""
        if "_" in codename:
            action, _model = codename.split("_", 1)
            if action in action_map:
                try:
                    # 基于 content_type 反推模型中文名，拼装成统一的 CRUD 权限文案。
                    model_cn = ContentTypeSerializer(context=self.context).get_model_cn(
                        obj.content_type
                    )
                    return f"{action_map[action]}{model_cn}"
                except Exception:
                    # 翻译失败时回退原始名称，保证接口稳定返回。
                    pass

        return obj.name


# 特定操作使用的序列化器


class UserGroupOperationSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的用户ID列表",
    )

    # 在序列化阶段先校验用户是否存在，避免在视图层再处理 DoesNotExist
    def validate_user_ids(self, value):
        # 条件：提交的 ID 数量与数据库命中数不一致；动作：抛错；结果：阻断无效批量操作。
        if not User.objects.filter(id__in=value).count() == len(set(value)):
            raise serializers.ValidationError("一个或多个用户ID无效。")
        return value


class PermissionAssignToUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="目标用户ID")
    # 如需一次分配多个权限，可在请求体中增加 permission_ids
    # 当前场景为单权限分配：权限由 URL 中的 pk 指定，用户由请求体中的 user_id 指定

    def validate_user_id(self, value):
        # 单用户权限操作需先保证目标用户存在，避免后续视图层重复判空。
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户ID无效。")
        return value


class PermissionAssignToGroupSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(help_text="目标用户组ID")

    def validate_group_id(self, value):
        # 单用户组权限操作需先保证目标用户组存在。
        if not Group.objects.filter(id=value).exists():
            raise serializers.ValidationError("指定的用户组ID无效。")
        return value


# 批量权限操作序列化器
class BatchPermissionOperationSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        help_text="要操作的权限ID列表",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：提交 ID 中存在重复或不存在项；动作：报错；结果：保证批量写入对象集合可完整命中。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class BatchUserPermissionOperationSerializer(BatchPermissionOperationSerializer):
    """批量用户权限操作序列化器"""

    pass


class BatchGroupPermissionOperationSerializer(BatchPermissionOperationSerializer):
    """批量用户组权限操作序列化器"""

    pass


class UpdateUserPermissionsSerializer(serializers.Serializer):
    """更新用户权限序列化器 - 用于完全替换用户的直接权限列表"""

    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,  # 允许空列表，表示清空所有直接权限
        help_text="要设置的权限ID列表，将完全替换用户当前的直接权限",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：权限 ID 非法；动作：阻断更新；结果：避免 set() 后出现不可预期的部分更新。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class UpdateGroupPermissionsSerializer(serializers.Serializer):
    """更新用户组权限序列化器 - 用于完全替换用户组的权限列表"""

    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,  # 允许空列表，表示清空所有权限
        help_text="要设置的权限ID列表，将完全替换用户组当前的权限",
    )

    def validate_permission_ids(self, value):
        from django.contrib.auth.models import Permission

        if not value:  # 如果是空列表，直接返回
            return value

        # 检查所有权限ID是否有效
        existing_count = Permission.objects.filter(id__in=value).count()
        # 条件：权限 ID 非法；动作：阻断更新；结果：避免用户组权限被写入不完整集合。
        if existing_count != len(set(value)):
            raise serializers.ValidationError("一个或多个权限ID无效。")
        return value


class UserApprovalReviewSerializer(serializers.Serializer):
    review_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
        help_text="审核备注，可选",
    )


class CurrentUserProfileSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=30)
    real_name = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def update(self, instance, validated_data):
        instance.email = validated_data["email"]
        instance.save(update_fields=["email"])

        profile = ensure_user_profile(instance)
        profile.phone_number = validated_data.get("phone_number", profile.phone_number)
        profile.real_name = validated_data.get("real_name", profile.real_name)
        profile.save(update_fields=["phone_number", "real_name", "updated_at"])
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "两次输入的新密码不一致。"})
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "当前密码不正确。"})
        return attrs


class MyTokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    # 覆盖默认的错误消息，使其更友好
    default_error_messages = {"no_active_account": "账号或密码错误"}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # 您可以在这里添加自定义声明到 token 中，如果需要的话
        # 示例：可在此向 token 写入用户名声明。
        return token

    def validate(self, attrs):
        # 先走父类认证校验，再附加用户信息以减少前端二次请求。
        data = super().validate(attrs)

        # 添加用户基础信息
        user_serializer = UserDetailSerializer(self.user)
        data["user"] = user_serializer.data

        return data
