import { BaseRoot } from './baseRoot';
import axios from 'axios';
import { getAuthHeader, clearAccessToken } from './auth';

// 添加请求拦截器确保所有请求都包含认证头
axios.interceptors.request.use(
  config => {
    // 为所有非登录/注册请求添加认证头
    if (!config.url.includes('/login_user') && !config.url.includes('/register_user')) {
      const authHeader = getAuthHeader();
      config.headers = {
        ...config.headers,
        ...authHeader
      };
    }
    // console.log('请求配置:', config); // 调试日志
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 添加响应拦截器处理401和403错误
axios.interceptors.response.use(
  response => {
    // 对于成功的响应，直接返回
    return response;
  },
  error => {
    // 处理错误响应
    if (error.response) {
      const { status } = error.response;
      
      // 处理401错误（访问令牌校验失败）
      if (status === 401) {
        alert('安全校验未通过：' + (error.response.data.message || '您无权访问系统'));
        // 清除本地存储的令牌
        clearAccessToken();
        // 重定向到登录页面
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
      // 处理403错误（用户权限验证失败）
      else if (status === 403) {
        // 显示权限不足的提示信息
        if (typeof window !== 'undefined' && window.alert) {
          alert('权限不足：' + (error.response.data.message || '您无权访问此资源'));
        }
      }
    }
    return Promise.reject(error);
  }
);



export const LoginApi = (loginData) => {
	return axios.post(`${BaseRoot}/login_user`, loginData);
};


export const RegisterApi = (registerData) => {
	return axios.post(`${BaseRoot}/register_user`, registerData);
};


export const ToolsApi = () => {
	return axios.get(`${BaseRoot}/get_all_tools`);
};

export const DeleteAllToolApi = () => {
	return axios.get(`${BaseRoot}/delete_all_tool`);
};

export const DeleteOneToolApi = (ids) => {
	return axios.post(`${BaseRoot}/delete_tool_by_ids`, ids);
};

export const UploadToolApi = async (file) => {
	const formData = new FormData();
  formData.append('file', file);
  
  // 让axios自动设置Content-Type为multipart/form-data
  return await axios.post(`${BaseRoot}/upload_tool`, formData).then(res=>{
    if(res.status === 200){
      return {
        status: 'success',
        message: '上传成功'
      }
    }
  }).catch(err=>{
    return {
      status: 'error',
      message: '上传失败：' + err.message
    }
  })
};


export const TestLLMApi = async (data) => {
  return axios.post(`${BaseRoot}/test_llm`, data);
};

export const ApiPlanningApi = async (data) => {
  return axios.post(`${BaseRoot}/api_planning`, data);
};



export const TestTaskStatusApi = async (data) => {
  return axios.post(`${BaseRoot}/api_task_status`, data);
};