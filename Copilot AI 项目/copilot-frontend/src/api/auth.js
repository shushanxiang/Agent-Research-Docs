// 认证工具函数

/**
 * 获取存储在localStorage中的访问令牌
 * @returns {string|null} 访问令牌或null
 */
export const getAccessToken = () => {
  return localStorage.getItem('access_token');
};

/**
 * 清除存储的访问令牌
 */
export const clearAccessToken = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('token_expires_in');
};

/**
 * 检查访问令牌是否存在
 * @returns {boolean} 是否存在有效的访问令牌
 */
export const isAuthenticated = () => {
  const token = getAccessToken();
  return !!token;
};

/**
 * 构造Authorization头
 * @returns {Object} 包含Authorization头的对象
 */
export const getAuthHeader = () => {
  const token = getAccessToken();
  // console.log('获取令牌:', token); // 调试日志
  if (token) {
    const authHeader = {
      Authorization: `Bearer ${token}`
    };
    // console.log('生成认证头:', authHeader); // 调试日志
    return authHeader;
  }
  // console.log('未找到令牌，返回空对象'); // 调试日志
  return {};
};