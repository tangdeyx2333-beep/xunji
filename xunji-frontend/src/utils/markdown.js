// src/utils/markdown.js
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

// 引入代码高亮样式 (你可以换成 github.css, monokai.css 等)
import 'highlight.js/styles/atom-one-dark.css' 

const md = new MarkdownIt({
  html: true,        // 允许 HTML 标签
  linkify: true,     // 自动识别链接
  typographer: true, // 优化排版
  highlight: function (str, lang) {
    // 自动代码高亮逻辑
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
      } catch (__) {}
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
})

export default function renderMarkdown(text) {
  return md.render(text || '')
}