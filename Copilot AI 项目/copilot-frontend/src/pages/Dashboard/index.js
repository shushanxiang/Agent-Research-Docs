import { Layout } from 'antd';
import TopNav from '../../components/TopNav';
import AppSidebar from '../../components/Sidebar';
import { Outlet } from 'react-router-dom';

const { Content } = Layout;

export default function Dashboard() {
  return (
    <Layout className="dashboard-layout">
      <AppSidebar />
      <Layout>
        <Content className="main-content">
          <Outlet />  {/* 路由出口 */}
        </Content>
      </Layout>
    </Layout>
  );
}