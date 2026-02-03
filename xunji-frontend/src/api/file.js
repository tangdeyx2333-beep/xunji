// src/api/file.js
import request from '@/utils/request'

// 1. 获取文件列表
export function getFiles() {
  return request({
    url: '/api/files',
    method: 'get'
  })
}

// 2. 上传文件
export function uploadFile(formData) {
  return request({
    url: '/api/upload',
    method: 'post',
    data: formData,
    // 上传文件必须设置这个 Header，虽然 axios 通常会自动处理，但写上更保险
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function deleteFile(fileId) {
  return request({
    url: `/api/files/${fileId}`,
    method: 'delete'
  })
}

export function clearKnowledgeBase() {
  return request({
    url: '/api/knowledge-base/clear',
    method: 'post',
    data: { confirm: true }
  })
}
