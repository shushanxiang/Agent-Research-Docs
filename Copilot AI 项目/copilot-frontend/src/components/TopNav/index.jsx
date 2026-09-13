import { Layout, Dropdown, Button } from 'antd';
// 添加图标导入
import { UserOutlined, LogoutOutlined } from '@ant-design/icons';

const { Header } = Layout;

export default function TopNav() {
  const handleLogout = () => {
    // 清除认证信息
    localStorage.removeItem('token');
    window.location.href = '/login';
  };

  return (
    <Header className="app-header" style={{ padding: '0 24px' }}>
      <div className="header-content" style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          // 修改后的用户图标部分
          <UserOutlined style={{ color: '#fff', fontSize: 18, marginRight: 12 }} />
          <Button
            type="primary"
            danger
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            className="logout-btn"
          >
            退出
          </Button>
        </div>
      </div>
    </Header>
  );
}