from rest_framework import serializers
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from .models import (
    TestCase,
    TestCaseStep,
    TestCaseModule,
    TestCaseScreenshot,
    TestSuite,
    TestBug,
    TestBugAttachment,
    TestBugActivity,
    TestExecution,
    TestCaseResult,
)
from projects.models import Project  # 确保导入Project模型以便进行校验
from accounts.serializers import UserDetailSerializer  # 用于显示创建者信息
from django.db import transaction


class TestCaseStepSerializer(serializers.ModelSerializer):
    """
    用例步骤序列化器
    """



    id = serializers.IntegerField(required=False)  # 在更新时用于标识现有步骤

    class Meta:
        model = TestCaseStep
        fields = [
            "id",
            "step_number",
            "description",
            "expected_result",
            "creator",
        ]  # creator 仅用于创建时关联
        read_only_fields = ["creator"]  # 通常在创建时由视图设置

    def create(self, validated_data):
        # creator 应该由视图的 perform_create 或序列化器的 save 方法中传递
        # 此处仅为示例，实际创建逻辑在 TestCaseSerializer 中处理
        return super().create(validated_data)


class TestCaseSerializer(serializers.ModelSerializer):
    """
    用例序列化器，支持嵌套创建和更新用例步骤
    """

    steps = TestCaseStepSerializer(many=True)
    screenshots = serializers.SerializerMethodField()
    creator_detail = UserDetailSerializer(source="creator", read_only=True)
    assignee_detail = serializers.SerializerMethodField()
    module_id = serializers.PrimaryKeyRelatedField(
        queryset=TestCaseModule.objects.all(),
        source="module",  # 关联到模型中的 'module' 字段
        allow_null=False,  # 不允许为空
        required=True,  # 创建时必须选择模块，PATCH请求时如果传入则必须验证
    )
    module_detail = serializers.StringRelatedField(
        source="module", read_only=True
    )  # 用于只读展示模块名称

    # project 字段在创建时需要，但通常通过 URL 传递，不在请求体中
    # project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all()) # 可以取消注释用于校验

    class Meta:
        model = TestCase
        fields = [
            "id",
            "project",
            "module_id",
            "module_detail",
            "name",
            "precondition",
            "level",
            "notes",
            "steps",
            "screenshot",
            "screenshots",
            "assignee_detail",
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
            "review_status",
            "test_type",
            "execution_status",
            "executed_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "module_detail",  # module_detail 仅用于展示
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
            "executed_at",
        ]
        # project 字段在创建时是必需的，但通常从 URL 获取，不在 request.data 中。
        # 如果要通过 request.data 传递 project_id，则需要将其从 read_only_fields 中移除，
        # 并在视图中处理或使用 HiddenField/SerializerMethodField 等。
        # 这里我们假设 project 将从 URL 传递给视图，并在视图的 perform_create 中设置。
        # 因此，对于序列化器本身，project 字段可以被视为只读或在创建时不直接通过此序列化器输入。
        # 为了简单起见，我们先将其保留在 fields 中，视图将负责处理其赋值。

    def _validate_unique_name_in_module(self, attrs):
        raw_name = attrs.get("name", getattr(self.instance, "name", ""))
        name = str(raw_name or "").strip()
        module = attrs.get("module", getattr(self.instance, "module", None))

        if not name or module is None:
            return

        duplicate_queryset = TestCase.objects.filter(module=module, name=name)
        if self.instance is not None:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)

        if duplicate_queryset.exists():
            raise serializers.ValidationError(
                {"name": f'模块“{module.name}”下已存在同名测试用例“{name}”'}
            )

    def validate(self, attrs):
        """验证数据"""
        # 创建时必须选择模块
        if self.instance is None and "module" not in attrs:
            raise serializers.ValidationError({"module_id": "请选择所属模块"})

        # 更新时如果传入了模块字段，则必须验证
        if self.instance and "module" in attrs and attrs["module"] is None:
            raise serializers.ValidationError({"module_id": "请选择所属模块"})

        self._validate_unique_name_in_module(attrs)
        return attrs

    def create(self, validated_data):
        steps_data = validated_data.pop("steps")
        # project 实例已在 validated_data 中由 perform_create 注入
        # creator 实例也已在 validated_data 中由 perform_create 注入
        test_case = TestCase.objects.create(**validated_data)
        for step_data in steps_data:
            # 确保步骤的 creator 与用例的 creator 一致
            TestCaseStep.objects.create(
                test_case=test_case, creator=test_case.creator, **step_data
            )
        return test_case

    @transaction.atomic
    def update(self, instance, validated_data):
        steps_data = validated_data.pop("steps", None)
        new_execution_status = validated_data.get("execution_status")

        # 更新 TestCase 实例的字段
        if "name" in validated_data:
            instance.name = validated_data["name"]
        if "precondition" in validated_data:
            instance.precondition = validated_data["precondition"]
        if "level" in validated_data:
            instance.level = validated_data["level"]
        if "module" in validated_data:
            instance.module = validated_data["module"]
        if "notes" in validated_data:
            instance.notes = validated_data["notes"]
        if "review_status" in validated_data:
            instance.review_status = validated_data["review_status"]
        if "test_type" in validated_data:
            instance.test_type = validated_data["test_type"]
        if "execution_status" in validated_data:
            instance.execution_status = validated_data["execution_status"]
            if new_execution_status in {"passed", "failed"}:
                instance.executed_at = timezone.now()

        # project 和 creator 通常不允许通过此接口更新
        instance.save()

        if steps_data is not None:
            existing_steps = {step.id: step for step in instance.steps.all()}
            step_ids_from_payload = set()
            final_steps_to_process = []  # 用于收集将要保存的步骤（新的或更新的）

            # 遍历传入的步骤数据
            for step_data in steps_data:
                step_id = step_data.get("id")
                step_creator = instance.creator  # 步骤的创建者应与用例的创建者一致

                if step_id:
                    step_ids_from_payload.add(step_id)
                    if step_id in existing_steps:
                        # 更新现有步骤
                        step_instance = existing_steps[step_id]
                        step_instance.description = step_data.get(
                            "description", step_instance.description
                        )
                        step_instance.expected_result = step_data.get(
                            "expected_result", step_instance.expected_result
                        )
                        # step_number 将在后面统一重新分配
                        final_steps_to_process.append(step_instance)
                    else:
                        # 如果提供了ID但步骤不存在，可以选择忽略或创建（这里选择忽略，避免意外创建）
                        # 或者可以引发一个 ValidationError
                        # 如需严格校验，可在此抛出“步骤不存在”异常。
                        pass
                else:
                    # 创建新步骤 (但不立即保存，也不立即分配 step_number)
                    new_step = TestCaseStep(
                        test_case=instance,
                        creator=step_creator,
                        description=step_data.get("description"),
                        expected_result=step_data.get("expected_result"),
                        # step_number 将在后面统一重新分配
                    )
                    final_steps_to_process.append(new_step)

            # 删除不再需要的步骤
            step_ids_to_delete = set(existing_steps.keys()) - step_ids_from_payload
            if step_ids_to_delete:
                TestCaseStep.objects.filter(
                    id__in=step_ids_to_delete, test_case=instance
                ).delete()

            # 为避免 unique constraint 冲突,先将所有现有步骤的 step_number 设置为临时大数值
            # 使用 10000 + id 作为临时值,确保不与正常编号(1,2,3...)冲突
            for step_obj in final_steps_to_process:
                if step_obj.id:  # 只对已存在的步骤设置临时值
                    step_obj.step_number = 10000 + step_obj.id  # 使用大数值作为临时值
                    step_obj.save()

            # 然后重新编号并保存所有步骤
            for index, step_obj in enumerate(final_steps_to_process):
                step_obj.step_number = index + 1
                step_obj.save()  # 这会处理创建新步骤或更新现有步骤的最终编号

        return instance

    def get_screenshots(self, obj):
        """获取测试用例的所有截屏"""
        screenshots = obj.screenshots.all()
        # 移除 context=self.context，确保 screenshot_url 生成相对路径
        return TestCaseScreenshotSerializer(screenshots, many=True).data

    def get_assignee_detail(self, obj):
        assignment = getattr(obj, "assignment", None)
        assignee = getattr(assignment, "assignee", None)
        if assignee is None:
            return None
        return {
            "id": assignee.id,
            "username": assignee.username,
        }


class TestCaseListSerializer(serializers.ModelSerializer):
    """
    ?????????
    ??????????????????????????
    """

    creator_detail = serializers.SerializerMethodField()
    assignee_detail = serializers.SerializerMethodField()
    assignment_created_at = serializers.SerializerMethodField()
    related_bug_count = serializers.SerializerMethodField()
    module_id = serializers.PrimaryKeyRelatedField(source="module", read_only=True)
    module_detail = serializers.StringRelatedField(source="module", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "project",
            "module_id",
            "module_detail",
            "name",
            "precondition",
            "level",
            "creator",
            "creator_detail",
            "assignee_detail",
            "assignment_created_at",
            "created_at",
            "updated_at",
            "review_status",
            "test_type",
            "related_bug_count",
            "execution_status",
            "executed_at",
        ]
        read_only_fields = fields

    def get_creator_detail(self, obj):
        creator = getattr(obj, "creator", None)
        if creator is None:
            return None
        return {
            "id": creator.id,
            "username": creator.username,
        }

    def get_assignee_detail(self, obj):
        assignment = getattr(obj, "assignment", None)
        assignee = getattr(assignment, "assignee", None)
        if assignee is None:
            return None
        return {
            "id": assignee.id,
            "username": assignee.username,
        }

    def get_assignment_created_at(self, obj):
        assignment = getattr(obj, "assignment", None)
        created_at = getattr(assignment, "created_at", None)
        return created_at

    def get_related_bug_count(self, obj):
        candidate_relations = (
            "bugs",
            "bug_links",
            "defects",
            "defect_links",
            "issues",
            "issue_links",
            "related_bugs",
            "related_defects",
            "related_issues",
        )

        for relation_name in candidate_relations:
            relation = getattr(obj, relation_name, None)
            if relation is None:
                continue

            if hasattr(relation, "count"):
                try:
                    return int(relation.count())
                except TypeError:
                    pass

            if isinstance(relation, (list, tuple, set)):
                return len(relation)

        return 0


class TestCaseModuleSerializer(serializers.ModelSerializer):
    """
    用例模块序列化器
    """


    creator_detail = UserDetailSerializer(source="creator", read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=TestCaseModule.objects.all(),
        source="parent",
        required=False,
        allow_null=True,
    )
    # 添加用例数量字段
    testcase_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseModule
        fields = [
            "id",
            "project",
            "name",
            "parent",
            "parent_id",
            "level",
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
            "testcase_count",  # 添加到字段列表
        ]
        read_only_fields = [
            "id",
            "project",
            "level",
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
        ]

    # 添加获取用例数量的方法
    def get_testcase_count(self, obj):
        """
        计算模块下的用例数量（包含所有子模块的用例）
        """
        annotated_count = getattr(obj, "testcase_count", None)
        if annotated_count is not None:
            return int(annotated_count)
        return TestCase.objects.filter(module_id=obj.id).count()

    def validate(self, attrs):
        """验证模块数据"""
        # 创建时，确保父模块属于同一个项目
        if self.instance is None and "parent" in attrs and attrs["parent"]:
            project = self.context["project"]
            parent = attrs["parent"]
            if parent.project_id != project.id:
                raise serializers.ValidationError(
                    {"parent": "父模块必须属于同一个项目"}
                )

            # 验证模块级别不超过5级
            if parent.level >= 5:
                raise serializers.ValidationError({"parent": "模块级别不能超过5级"})

        # 更新时，确保父模块属于同一个项目
        elif self.instance and "parent" in attrs and attrs["parent"]:
            parent = attrs["parent"]
            if parent.project_id != self.instance.project_id:
                raise serializers.ValidationError(
                    {"parent": "父模块必须属于同一个项目"}
                )

            # 验证模块级别不超过5级
            if parent.level >= 5:
                raise serializers.ValidationError({"parent": "模块级别不能超过5级"})

            # 验证父模块不是自己或自己的子模块（避免循环引用）
            if parent.id == self.instance.id:
                raise serializers.ValidationError({"parent": "父模块不能是自己"})

            # 检查是否会形成循环引用
            current_parent = parent
            while current_parent:
                if current_parent.parent_id == self.instance.id:
                    raise serializers.ValidationError(
                        {"parent": "不能选择自己的子模块作为父模块"}
                    )
                current_parent = current_parent.parent

        return attrs

    def create(self, validated_data):
        # project 实例已在 validated_data 中由 perform_create 注入
        # creator 实例也已在 validated_data 中由 perform_create 注入

        # 设置模块级别
        parent = validated_data.get("parent")
        if parent:
            validated_data["level"] = parent.level + 1
        else:
            validated_data["level"] = 1

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # 更新模块级别
        parent = validated_data.get("parent")
        if parent:
            validated_data["level"] = parent.level + 1
        elif "parent" in validated_data and validated_data["parent"] is None:
            validated_data["level"] = 1

        return super().update(instance, validated_data)


class TestCaseScreenshotSerializer(serializers.ModelSerializer):
    """
    测试用例截屏序列化器
    """



    uploader_detail = UserDetailSerializer(source="uploader", read_only=True)

    # 用于“读”操作：显示相对 URL
    screenshot_url = serializers.CharField(source="screenshot.url", read_only=True)

    # 用于“写”操作：接收上传的文件
    screenshot = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = TestCaseScreenshot
        fields = [
            "id",
            "test_case",
            "screenshot",  # 用于上传
            "screenshot_url",  # 用于显示
            "title",
            "description",
            "step_number",
            "created_at",
            "mcp_session_id",
            "page_url",
            "uploader",
            "uploader_detail",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "uploader",
            "uploader_detail",
            "screenshot_url",
        ]

    def create(self, validated_data):
        """创建截屏时自动设置上传人"""
        request = self.context.get("request")
        if request and request.user:
            validated_data["uploader"] = request.user
        return super().create(validated_data)


class TestSuiteSerializer(serializers.ModelSerializer):
    """
    测试套件序列化器
    """



    creator_detail = UserDetailSerializer(source="creator", read_only=True)
    testcase_count = serializers.SerializerMethodField()
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=TestSuite.objects.all(),
        source="parent",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = TestSuite
        fields = [
            "id",
            "name",
            "description",
            "project",
            "parent",
            "parent_id",
            "level",
            "testcase_count",
            "max_concurrent_tasks",
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "level",
            "creator",
            "creator_detail",
            "created_at",
            "updated_at",
        ]



    def get_testcase_count(self, obj):
        """获取套件中的用例数量"""
        annotated_count = getattr(obj, "testcase_count", None)
        if annotated_count is not None:
            return int(annotated_count)
        return obj.testcases.count()

    def validate(self, attrs):
        parent = attrs.get("parent")
        project_id = self.context.get("project_id") or getattr(self.instance, "project_id", None)

        if parent and parent.project_id != project_id:
            raise serializers.ValidationError({"parent": "父套件必须属于同一个项目"})

        if parent and parent.level >= 5:
            raise serializers.ValidationError({"parent": "套件级别不能超过5级"})

        if self.instance and parent:
            if parent.id == self.instance.id:
                raise serializers.ValidationError({"parent": "父套件不能是自己"})

            current_parent = parent
            while current_parent:
                if current_parent.parent_id == self.instance.id:
                    raise serializers.ValidationError({"parent": "不能选择自己的子套件作为父套件"})
                current_parent = current_parent.parent

        return attrs

    def validate_max_concurrent_tasks(self, value):
        """验证并发数配置"""
        if value < 1:
            raise serializers.ValidationError("并发数至少为1（串行执行）")
        if value > 10:
            raise serializers.ValidationError("并发数不能超过10，避免系统资源耗尽")
        return value

    def create(self, validated_data):
        parent = validated_data.get("parent")
        validated_data["level"] = parent.level + 1 if parent else 1
        return TestSuite.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get("description", instance.description)
        if "parent" in validated_data:
            instance.parent = validated_data.get("parent")
            instance.level = instance.parent.level + 1 if instance.parent else 1
        instance.max_concurrent_tasks = validated_data.get(
            "max_concurrent_tasks", instance.max_concurrent_tasks
        )
        instance.save()

        return instance


class TestBugSerializer(serializers.ModelSerializer):
    assigned_to_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    creator_detail = UserDetailSerializer(source="opened_by", read_only=True)
    assigned_to_detail = UserDetailSerializer(source="assigned_to", read_only=True)
    assigned_to_details = UserDetailSerializer(source="assigned_users", many=True, read_only=True)
    assigned_to_names = serializers.SerializerMethodField()
    assigned_to_ids_read = serializers.SerializerMethodField()
    resolved_by_detail = UserDetailSerializer(source="resolved_by", read_only=True)
    closed_by_detail = UserDetailSerializer(source="closed_by", read_only=True)
    activated_by_detail = UserDetailSerializer(source="activated_by", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    testcase_name = serializers.CharField(source="testcase.name", read_only=True)
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    bug_type_display = serializers.CharField(source="get_bug_type_display", read_only=True)
    resolution_display = serializers.CharField(source="get_resolution_display", read_only=True)
    attachments = serializers.SerializerMethodField()
    activity_logs = serializers.SerializerMethodField()

    class Meta:
        model = TestBug
        fields = [
            "id",
            "project",
            "suite",
            "suite_name",
            "testcase",
            "testcase_name",
            "title",
            "steps",
            "expected_result",
            "actual_result",
            "bug_type",
            "bug_type_display",
            "severity",
            "priority",
            "status",
            "status_display",
            "resolution",
            "resolution_display",
            "attachments",
            "activity_logs",
            "keywords",
            "deadline",
            "assigned_to",
            "assigned_to_ids",
            "assigned_to_ids_read",
            "assigned_to_names",
            "assigned_to_detail",
            "assigned_to_details",
            "opened_by",
            "creator_detail",
            "opened_at",
            "assigned_at",
            "resolved_by",
            "resolved_by_detail",
            "resolved_at",
            "closed_by",
            "closed_by_detail",
            "closed_at",
            "activated_by",
            "activated_by_detail",
            "activated_at",
            "activated_count",
            "solution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "opened_by",
            "creator_detail",
            "suite_name",
            "testcase_name",
            "status_display",
            "bug_type_display",
            "resolution_display",
            "assigned_to_detail",
            "assigned_to_details",
            "resolved_by_detail",
            "closed_by_detail",
            "activated_by_detail",
            "opened_at",
            "assigned_at",
            "resolved_at",
            "closed_at",
            "activated_at",
            "activated_count",
            "created_at",
            "updated_at",
        ]

    def get_status(self, obj):
        return obj.get_effective_status()

    def get_status_display(self, obj):
        return obj.get_effective_status_display()

    def get_assigned_to_names(self, obj):
        assigned_users = list(obj.assigned_users.all())
        return [user.username for user in assigned_users]

    def get_assigned_to_ids_read(self, obj):
        return list(obj.assigned_users.values_list("id", flat=True))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["assigned_to_ids"] = data.pop("assigned_to_ids_read", [])
        return data

    def _get_validated_assigned_users(self, attrs):
        assigned_to_ids = attrs.pop("assigned_to_ids", None)
        project = self.context.get("project") or getattr(self.instance, "project", None)

        if assigned_to_ids is None:
            assigned_user = attrs.get("assigned_to", serializers.empty)
            if assigned_user is serializers.empty:
                return None
            return [assigned_user] if assigned_user else []

        normalized_ids = []
        for user_id in assigned_to_ids:
            if user_id not in normalized_ids:
                normalized_ids.append(user_id)

        if not normalized_ids:
            attrs["assigned_to"] = None
            return []

        if project is None:
            raise serializers.ValidationError({"assigned_to_ids": "当前项目不存在"})

        members = list(
            User.objects.filter(
                id__in=normalized_ids,
                project_memberships__project=project,
            ).distinct()
        )
        member_map = {member.id: member for member in members}
        invalid_ids = [user_id for user_id in normalized_ids if user_id not in member_map]
        if invalid_ids:
            raise serializers.ValidationError({"assigned_to_ids": "指派人员必须是当前项目成员"})

        assigned_users = [member_map[user_id] for user_id in normalized_ids]
        attrs["assigned_to"] = assigned_users[0] if assigned_users else None
        return assigned_users

    def validate(self, attrs):
        instance = self.instance
        project = self.context.get("project")
        suite = attrs.get("suite", getattr(instance, "suite", None))
        testcase = attrs.get("testcase", getattr(instance, "testcase", None))

        if suite is None:
            raise serializers.ValidationError({"suite": "请选择所属测试套件"})

        project_obj = project or getattr(instance, "project", None)
        if project_obj and suite.project_id != project_obj.id:
            raise serializers.ValidationError({"suite": "测试套件必须属于当前项目"})

        if testcase is not None:
            if project_obj and testcase.project_id != project_obj.id:
                raise serializers.ValidationError({"testcase": "测试用例必须属于当前项目"})
            if testcase.id not in suite.testcases.values_list("id", flat=True):
                raise serializers.ValidationError({"testcase": "只能关联当前套件中的测试用例"})

        return attrs

    def create(self, validated_data):
        assigned_users = self._get_validated_assigned_users(validated_data)
        bug = super().create(validated_data)
        if assigned_users is not None:
            bug.assigned_users.set(assigned_users)
        return bug

    def update(self, instance, validated_data):
        assigned_users = self._get_validated_assigned_users(validated_data)
        bug = super().update(instance, validated_data)
        if assigned_users is not None:
            bug.assigned_users.set(assigned_users)
        return bug

    def get_attachments(self, obj):
        try:
            attachments = obj.attachments.select_related("uploaded_by").all()
            return TestBugAttachmentSerializer(attachments, many=True, context=self.context).data
        except (OperationalError, ProgrammingError):
            return []

    def get_activity_logs(self, obj):
        try:
            activities = obj.activities.select_related("operator").all().order_by("-created_at")
            return TestBugActivitySerializer(activities, many=True, context=self.context).data
        except (OperationalError, ProgrammingError):
            return []


class TestBugAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = TestBugAttachment
        fields = [
            "id",
            "bug",
            "section",
            "attachment",
            "url",
            "original_name",
            "file_type",
            "content_type",
            "file_size",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        if not obj.attachment:
            return ""
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url


class TestBugListSerializer(serializers.ModelSerializer):
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    testcase_name = serializers.CharField(source="testcase.name", read_only=True)
    testcase_names = serializers.SerializerMethodField()
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True)
    assigned_to_names = serializers.SerializerMethodField()
    assigned_to_ids = serializers.SerializerMethodField()
    opened_by_name = serializers.CharField(source="opened_by.username", read_only=True)
    resolved_by_name = serializers.CharField(source="resolved_by.username", read_only=True)
    bug_type_display = serializers.CharField(source="get_bug_type_display", read_only=True)
    status = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    resolution_display = serializers.CharField(source="get_resolution_display", read_only=True)

    class Meta:
        model = TestBug
        fields = [
            "id",
            "suite",
            "suite_name",
            "testcase",
            "testcase_name",
            "testcase_names",
            "title",
            "bug_type",
            "bug_type_display",
            "severity",
            "priority",
            "status",
            "status_display",
            "resolution",
            "resolution_display",
            "assigned_to",
            "assigned_to_name",
            "assigned_to_names",
            "assigned_to_ids",
            "opened_by",
            "opened_by_name",
            "opened_at",
            "assigned_at",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "closed_at",
            "activated_at",
            "activated_count",
            "deadline",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return obj.get_effective_status()

    def get_status_display(self, obj):
        return obj.get_effective_status_display()

    def get_assigned_to_names(self, obj):
        return [user.username for user in obj.assigned_users.all()]

    def get_assigned_to_ids(self, obj):
        return list(obj.assigned_users.values_list("id", flat=True))

    def get_testcase_names(self, obj):
        names = list(obj.related_testcases.values_list("name", flat=True))
        if names:
            return names
        return [obj.testcase.name] if obj.testcase_id and obj.testcase else []


from urllib.parse import urlparse


class TestCaseResultSerializer(serializers.ModelSerializer):
    """
    测试用例执行结果序列化器
    """



    testcase_detail = TestCaseSerializer(source="testcase", read_only=True)
    duration = serializers.ReadOnlyField()
    screenshots = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseResult
        fields = [
            "id",
            "execution",
            "testcase",
            "testcase_detail",
            "status",
            "error_message",
            "stack_trace",
            "started_at",
            "completed_at",
            "execution_time",
            "duration",
            "mcp_session_id",
            "screenshots",
            "execution_log",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "duration"]

    def get_screenshots(self, obj):
        """确保返回的截图URL是相对路径"""
        if not obj.screenshots:
            return []

        relative_urls = []
        for url in obj.screenshots:
            if url:
                # 解析URL，只取路径部分
                parsed_url = urlparse(url)
                relative_urls.append(parsed_url.path)
        return relative_urls


class TestExecutionSerializer(serializers.ModelSerializer):
    """
    测试执行记录序列化器
    """



    suite_detail = TestSuiteSerializer(source="suite", read_only=True)
    executor_detail = UserDetailSerializer(source="executor", read_only=True)
    results = TestCaseResultSerializer(many=True, read_only=True)
    duration = serializers.ReadOnlyField()
    pass_rate = serializers.ReadOnlyField()

    class Meta:
        model = TestExecution
        fields = [
            "id",
            "suite",
            "suite_detail",
            "status",
            "executor",
            "executor_detail",
            "started_at",
            "completed_at",
            "total_count",
            "passed_count",
            "failed_count",
            "skipped_count",
            "error_count",
            "celery_task_id",
            "duration",
            "pass_rate",
            "results",
            "generate_playwright_script",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "started_at",
            "completed_at",
            "total_count",
            "passed_count",
            "failed_count",
            "skipped_count",
            "error_count",
            "celery_task_id",
            "duration",
            "pass_rate",
            "created_at",
            "updated_at",
        ]


class TestBugActivitySerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="operator.username", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = TestBugActivity
        fields = [
            "id",
            "bug",
            "action",
            "action_display",
            "content",
            "metadata",
            "operator",
            "operator_name",
            "created_at",
        ]
        read_only_fields = fields


class TestExecutionCreateSerializer(serializers.Serializer):
    """
    创建测试执行的简化序列化器
    """

    suite_id = serializers.IntegerField(required=True, help_text="测试套件ID")
    generate_playwright_script = serializers.BooleanField(
        required=False, default=False, help_text="是否为功能测试用例生成Playwright脚本"
    )

    def validate_suite_id(self, value):
        """验证套件是否存在"""
        try:
            suite = TestSuite.objects.get(id=value)
            # 验证套件是否有测试用例
            if not suite.testcases.exists():
                raise serializers.ValidationError("测试套件中没有测试用例")
            return value
        except TestSuite.DoesNotExist:
            raise serializers.ValidationError("测试套件不存在")
