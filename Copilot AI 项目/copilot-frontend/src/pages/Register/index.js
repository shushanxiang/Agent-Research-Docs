import { Form, Input, Button, Typography,message } from 'antd';
import { UserOutlined, PhoneOutlined, LockOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { RegisterApi } from '../../api/agent';
import './style.css';

export default function Register() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();

  const handleSubmit = () => {
    console.log(form.getFieldsValue())
    RegisterApi(form.getFieldsValue()).then(res => {
      if (res.status === 200) {
        navigate('/login');
      }
    }).catch(err => {
      let errorMessage = '注册失败'; 

          if (err.response && err.response.data && err.response.data.message) {
            errorMessage = err.response.data.message; 
          } else if (err.message) {
            errorMessage = err.message;
          }

          messageApi.open({
            type: 'error',
            content: errorMessage, 
            duration: 5,
          });

          console.error('Registration failed:', err.response || err);
    })
	};

  return (
    <div className="register-container">
      {contextHolder}
      <div className="register-card">
        <Typography.Title level={2} className="neon-title">
          用户注册
        </Typography.Title>
        
        <Form form={form} className="dark-form">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入昵称!' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="昵称"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码!' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item
            name="confirm"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码!' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject('两次输入的密码不一致!');
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="确认密码"
            />
          </Form.Item>

          <Button
            type="primary"
            block
            onClick={handleSubmit}
            className="register-btn"
          >
            立即注册
          </Button>

          <div className="login-link">
            已有账号？<Link to="/login">立即登录</Link>
          </div>
        </Form>
      </div>
    </div>
  );
}