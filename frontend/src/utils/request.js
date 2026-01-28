import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 在发送请求之前做些什么
    // 可以在这里添加token等认证信息
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  error => {
    // 对请求错误做些什么
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    // 对响应数据做点什么
    const res = response.data
    // 如果是下载文件，直接返回response
    if (response.config.responseType === 'blob') {
      return response
    }
    // 根据后端API的返回格式进行处理
    if (res.code === 0) {
      return res.data
    } else {
      // 处理错误
      console.error('Response error:', res.msg)
      return Promise.reject(new Error(res.msg || '请求失败'))
    }
  },
  error => {
    // 对响应错误做点什么
    console.error('Response error:', error)
    return Promise.reject(error)
  }
)

export default request
