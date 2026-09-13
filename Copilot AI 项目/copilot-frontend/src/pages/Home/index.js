import { Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import './style.css';

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="hero-section">
      <img src="/logo512.png" className="main-logo" />
      <div className="button-group">
        <Button 
          type="primary" 
          size="large"
          shape="round"
          className="login-btn"
          onClick={() => navigate('/login')}
        >
          立即登录
        </Button>
        <Button 
          size="large"
          shape="round"
          className="register-btn"
          onClick={() => navigate('/register')}
        >
          新用户注册
        </Button>
      </div>
    </div>
  );
}