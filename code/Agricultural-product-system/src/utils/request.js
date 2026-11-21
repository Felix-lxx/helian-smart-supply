import axios from 'axios'
import { ElMessage } from 'element-plus'
// 注意：这里保留导入，但不在顶层直接逻辑中使用它
import router from '../router'

const service = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 5000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 每次请求动态附加 token，避免手写重复鉴权头。
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => response,
  error => {
    // 401 统一处理：清理本地登录态并跳转登录页。
    // 重点：在函数内部使用 router，避开初始化时的循环依赖
    if (error.response && error.response.status === 401) {
      for (const key of ['access_token', 'refresh_token', 'user_role', 'username', 'user_id']) {
        localStorage.removeItem(key)
      }
      ElMessage.error('登录凭证已过期，请重新登录')

      // 如果 router.push 还是报错，可以临时改用 window.location.href = '/login'
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default service
