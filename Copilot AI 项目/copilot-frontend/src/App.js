import logo from './logo.svg';
import './App.css';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './pages/Home';
import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import { Layout, ConfigProvider } from 'antd';
import { useWindowSize } from 'react-use';
import Dashboard from './pages/Dashboard';
import { useState } from 'react';
import ApiTools from './pages/ApiTools';
import Copilot from './pages/Coplilot';
import Graph from './pages/Graph';

function App() {
  const [collapsed, setCollapsed] = useState(false);
  const { width } = useWindowSize();
  return (
    <ConfigProvider theme={{
      token: {
        colorPrimary: '#1890ff',
        borderRadius: 8,
      },
    }}>
      <Layout style={{ minHeight: '100vh' }}>
          <Router>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              // 添加路由配置

              
              // 在已有路由结构中增加
              // 更新路由配置
              <Route path="/dashboard" element={<Dashboard />}>
                <Route path="api-tools" element={<ApiTools />} />
                <Route path="copilot" element={<Copilot />} />
              </Route>
            </Routes>
          </Router>
      </Layout>
    </ConfigProvider>
  );
}

export default App;
