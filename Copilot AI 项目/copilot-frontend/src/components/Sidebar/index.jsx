import { useState } from 'react';
import { Layout, Menu, Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { ApiOutlined, RobotOutlined, ThunderboltOutlined, CloseOutlined } from '@ant-design/icons';
import { LogoutOutlined } from '@ant-design/icons';

const { Sider } = Layout;

export default function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  const menuItems = [
    {
      key: 'api-tools',
      icon: <ApiOutlined />,
      label: 'API工具',
      onClick: () => navigate('/dashboard/api-tools')
    },
    {
      key: 'copilot',
      icon: <ThunderboltOutlined />,
      label: 'Copilot执行',
      onClick: () => navigate('/dashboard/copilot')
    }
  ];

  const handleLogout = () => {
    // 退出登录逻辑（需根据实际认证方案实现）
    localStorage.removeItem('token');
    window.location.href = '/login';
  };

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      className="glow-sidebar"
      width={250}
    >
       
     
      <div className="header-content" style={{ display: 'flex', alignItems: 'center',margin:10 }}>
        <img src="/logo192.png" className="nav-logo" style={{ width: 32, marginRight: 12,marginLeft:12 }} />
        <span className="platform-name" style={{ color: '#fff', fontSize: 18 }}>Copilot智能操作平台</span>
        </div>
       <div className="sidebar-header">
      <Button
        type="primary"
        danger
        icon={<LogoutOutlined />}
        onClick={handleLogout}
        style={{
          position: 'absolute',
          top: 'calc(30% - 48px)',
          left: 24,
          right: 24,
          width: 'calc(100% - 48px)'
        }}
      >
        退出系统
      </Button>
      </div>
      <Menu
        theme="dark"
        mode="inline"
        items={menuItems}
        className="nav-menu"
        style={{ marginTop: '40px', gap: '8px' }}
      />
     
    </Sider>
  );
}
