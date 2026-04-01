from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.views import MyTokenObtainPairView


class MyTokenObtainPairViewTests(SimpleTestCase):
    def setUp(self):
        # 构造 DRF 请求工厂，模拟 token 登录请求。
        self.factory = APIRequestFactory()

    def test_returns_503_when_database_not_ready(self):
        # 模拟数据库尚未就绪时的登录请求，验证接口返回 503 而不是 500 traceback。
        request = self.factory.post(
            '/api/token/',
            {'username': 'tester', 'password': 'secret'},
            format='json'
        )

        # 条件：认证流程抛出 OperationalError；动作：调用视图；结果：返回友好错误提示。
        with patch(
            'accounts.views.BaseTokenObtainPairView.post',
            side_effect=OperationalError('database is not ready')
        ):
            response = MyTokenObtainPairView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['detail'], '认证服务正在启动，请稍后重试。')
