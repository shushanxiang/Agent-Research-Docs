import { Form, Input, Button, Typography,message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { LoginApi } from '../../api/agent';

import './style.css';

export default function LoginPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();

  const handleSubmit = () => {
    console.log('登录表单数据:', form.getFieldsValue())
    LoginApi(form.getFieldsValue()).then(res => {
      console.log('登录响应:', res);
         
      if (res.status === 200) {
        // 根据实际响应结构调整访问令牌数据的路径
        // 从最新的控制台输出可以看出，令牌数据在res.data.auth_data中
        const authData = res.data && res.data.auth_data;
        console.log('登录响应中的令牌:', authData);
        
        // // 显示authData的详细内容
        // if (authData) {
        //   console.log('authData的键:', Object.keys(authData));
        //   console.log('authData的完整内容:', authData);
          
        //   // 如果authData中有token对象，也显示其详细内容
        //   if (authData.token) {
        //     console.log('token的键:', Object.keys(authData.token));
        //     console.log('token的完整内容:', authData.token);
        //   }
        // }
        
        // 存储访问令牌
        if (authData && authData.token && authData.token.access_token) {
          console.log('存储令牌:', authData.token.access_token);
          localStorage.setItem('access_token', authData.token.access_token);
          localStorage.setItem('token_expires_in', authData.token.expires_in);
          console.log('localStorage中的令牌:', localStorage.getItem('access_token'));
        } else {
          console.log('响应中没有找到令牌:', authData);
          // 显示完整的响应数据以便调试
          // console.log('完整的响应数据:', res);
          // // 特别显示data对象的内容
          // if (res.data) {
          //   console.log('res.data的键:', Object.keys(res.data));
          //   console.log('res.data的完整内容:', res.data);
          // }
        }
        navigate('/dashboard/copilot');
      } else {
        messageApi.open({
          type: 'error',
          content: res.message || '登录失败',
          duration: 5,
        });
      }
    }).catch(err => {
      messageApi.open({
      type: 'error',
      content: '登录失败',
      duration: 5,
    });
      console.log('登录错误:', err);
    })
	};
  return (
    <div className="login-container">
      {contextHolder}
      <div className="login-card">
        <Typography.Title level={2} className="neon-title">
          Copilot 登录
        </Typography.Title>

        <Form form={form} className="light-form">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名!' }]}
          >
            <Input
              prefix={<UserOutlined  style={{ color: '#08c' }} />}
              placeholder="用户名"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码!' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#08c' }}/>}
              placeholder="密码"
            />
          </Form.Item>

          <Button
            type="primary"
            block
            onClick={handleSubmit}
            className="login-btn"
          >
            立即登录
          </Button>

          <div className="register-link">
            新用户？<Button type="link" onClick={() => navigate('/register')}>立即注册</Button>
          </div>
        </Form>
      </div>
    </div>
  );
}