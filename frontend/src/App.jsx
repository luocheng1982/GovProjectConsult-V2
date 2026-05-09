import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import axios from 'axios'
import { Send, Paperclip, Bot, User, Loader2, X, FileText, Trash2, PlusCircle, MessageSquare, Database, Download, ExternalLink, Edit2, Search, ThumbsUp, ThumbsDown } from 'lucide-react'

function App() {
  // 自动检测API地址
  const [API_BASE_URL] = useState(() => {
    if (typeof window === 'undefined') {
      return 'http://localhost:8000/api/v1'
    }
    const hostname = window.location.hostname
    console.log('[API CONFIG] Detected hostname:', hostname)
    
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8000/api/v1'
    }
    // 在网络环境下，使用当前主机IP
    return `http://${hostname}:8000/api/v1`
  })
  
  console.log('[API CONFIG] Using API Base URL:', API_BASE_URL)
  
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem('chat_sessions');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error("Failed to parse sessions from local storage", e);
      }
    }
    return [{
      id: Date.now(),
      title: '新对话',
      messages: [
        { role: 'assistant', content: '您好！我是政府项目咨询助手。请问有什么可以帮您？\n(例如：在项目开展过程中申请项目变更，有哪些注意事项？)', projectType: 'general' }
      ]
    }];
  })
  
  const [currentSessionId, setCurrentSessionId] = useState(() => {
      if (sessions && sessions.length > 0) return sessions[0].id;
      return Date.now();
  })
  
  // Ensure currentSessionId is valid
  useEffect(() => {
      if (sessions.length > 0 && !sessions.find(s => s.id === currentSessionId)) {
          setCurrentSessionId(sessions[0].id);
      }
  }, [sessions, currentSessionId]);

  // Persist sessions
  useEffect(() => {
      localStorage.setItem('chat_sessions', JSON.stringify(sessions));
  }, [sessions]);

  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [showKbModal, setShowKbModal] = useState(false)
  const [kbFiles, setKbFiles] = useState([])
  const [projectTypes, setProjectTypes] = useState([])
  const [currentProjectType, setCurrentProjectType] = useState('general')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadType, setUploadType] = useState('policy')
  const [isUploading, setIsUploading] = useState(false)
  const [showCreateTypeModal, setShowCreateTypeModal] = useState(false)
  const [newTypeName, setNewTypeName] = useState('')
  const [apiConnected, setApiConnected] = useState(true)
  
  // 检查API连接
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 3000)
        
        await axios.get(`${API_BASE_URL}/health`, { 
          signal: controller.signal,
          timeout: 3000
        })
        clearTimeout(timeoutId)
        setApiConnected(true)
        console.log('[API CONNECTED]:', API_BASE_URL)
      } catch (error) {
        console.warn('[API HEALTH CHECK FAILED]:', error.message)
        console.warn('This may be due to CORS or network settings. Chat functionality may still work.')
        // 不立即标记为断开，给聊天请求一个机会
        setApiConnected(true)
      }
    }
    checkConnection()
  }, [API_BASE_URL])
  const [newTypeId, setNewTypeId] = useState('')
  const [isGeneratingId, setIsGeneratingId] = useState(false)
  const [userRole, setUserRole] = useState(() => localStorage.getItem('user_role') || 'user')
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [loginPassword, setLoginPassword] = useState('')
  const [showEditTypeModal, setShowEditTypeModal] = useState(false)
  const [editTypeName, setEditTypeName] = useState('')
  const [showSourceModal, setShowSourceModal] = useState(false)
  const [activeSources, setActiveSources] = useState([])
  const kbFileInputRef = useRef(null)

  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const [streamingIndex, setStreamingIndex] = useState(null)
  const [streamingText, setStreamingText] = useState('')

  const currentSession = useMemo(() => {
    return sessions.find(s => s.id === currentSessionId) || sessions[0]
  }, [sessions, currentSessionId])
  const messages = useMemo(() => {
    if (!currentSession) return []
    if (streamingIndex === null) return currentSession.messages
    return currentSession.messages.map((m, idx) => {
      if (idx === streamingIndex && m.role === 'assistant') {
        return { ...m, content: streamingText }
      }
      return m
    })
  }, [currentSession, streamingIndex, streamingText])

  const fetchProjectTypes = useCallback(async () => {
    try {
        const res = await axios.get('/api/v1/project-types')
        setProjectTypes(res.data)
        if (res.data.length > 0) {
            // keep current if valid, else first
            // actually we can just default to 'general' or first one
        }
    } catch (e) {
        console.error("Failed to fetch project types", e)
    }
  }, [])

  useEffect(() => {
    fetchProjectTypes()
  }, [fetchProjectTypes])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleFileSelect = (event) => {
    const file = event.target.files[0]
    if (!file) return
    setSelectedFile(file)
    // Clear the input value so the same file can be selected again if needed
    event.target.value = ''
  }

  const removeSelectedFile = () => {
    setSelectedFile(null)
  }

  const startNewChat = () => {
    const newSession = {
      id: Date.now(),
      title: '新对话',
      messages: [
        { role: 'assistant', content: '您好！我是政府项目咨询助手。请问有什么可以帮您？\n(例如：在项目开展过程中申请项目变更，有哪些注意事项？)', projectType: 'general' }
      ]
    }
    setSessions(prev => [newSession, ...prev])
    setCurrentSessionId(newSession.id)
    setInput('')
    setSelectedFile(null)
  }

  const deleteSession = (e, id) => {
    e.stopPropagation()
    setSessions(prev => {
      const newSessions = prev.filter(s => s.id !== id)
      if (newSessions.length === 0) {
        const newSession = {
            id: Date.now(),
            title: '新对话',
            messages: [
              { role: 'assistant', content: '您好！我是政府项目咨询助手。请问有什么可以帮您？\n(例如：在项目开展过程中申请项目变更，有哪些注意事项？)', projectType: 'general' }
            ]
          }
        // setCurrentSessionId will be handled by useEffect or explicit set here if we want instant switch
        // But let's return the new state and let the component update
        // Actually, we need to update currentSessionId if we deleted the active one
        return [newSession]
      }
      return newSessions
    })
  }

  const updateSessionMessages = (sessionId, action) => {
    setSessions(prev => prev.map(session => {
      if (session.id === sessionId) {
        const newMessages = typeof action === 'function' ? action(session.messages) : action
        
        // Auto-update title
        let newTitle = session.title
        if (session.title === '新对话' && newMessages.length > 1) {
           const firstUserMsg = newMessages.find(m => m.role === 'user')
           if (firstUserMsg) {
               const content = firstUserMsg.content.replace(/^\[文件: .*?\]\n/, '')
               newTitle = content.slice(0, 10) + (content.length > 10 ? '...' : '')
           }
        }
        return { ...session, messages: newMessages, title: newTitle }
      }
      return session
    }))
  }

  const deleteMessage = (index) => {
    updateSessionMessages(currentSessionId, prev => prev.filter((_, i) => i !== index))
  }

  const handleFeedback = async (feedbackType, messageIndex, aiResponse) => {
    console.log('[FEEDBACK CLICKED:', { feedbackType, messageIndex })
    
    try {
      const currentSession = sessions.find(s => s.id === currentSessionId)
      const messages = currentSession?.messages || []
      const userMessage = messageIndex > 0 ? messages[messageIndex - 1]?.content : null
      const currentFeedback = messages[messageIndex]?.feedback
      
      console.log('[FEEDBACK CURRENT:', { currentFeedback, feedbackType })
      
      let newFeedbackType = feedbackType
      let isCancelling = false
      
      if (currentFeedback === feedbackType) {
        newFeedbackType = null
        isCancelling = true
      }
      
      console.log('[FEEDBACK NEW STATE:', { newFeedbackType, isCancelling })
      
      // 先更新本地状态，确保视觉效果立即显示
      updateSessionMessages(currentSessionId, prev => {
        const newMsgs = [...prev]
        if (newMsgs[messageIndex]) {
          newMsgs[messageIndex] = { 
            ...newMsgs[messageIndex], 
            feedback: newFeedbackType 
          }
        }
        return newMsgs
      })
      
      console.log('[FEEDBACK SENDING TO API...')
      
      // 再发送API请求
      const response = await axios.post(`${API_BASE_URL}/feedback`, {
        feedback_type: feedbackType,
        message_index: messageIndex,
        user_message: userMessage,
        ai_response: aiResponse,
        project_type: currentProjectType,
        is_cancel: isCancelling
      })
      
      console.log('[FEEDBACK API RESPONSE]:', response.data)
      
    } catch (error) {
      console.error('[FEEDBACK ERROR:', error.response || error.message)
      alert('反馈提交失败，请检查网络连接')
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = input
    const currentFile = selectedFile
    const activeSessionId = currentSessionId // Capture current session ID
    
    // Construct user message content
    let displayContent = userMessage
    if (currentFile) {
        displayContent = `[文件: ${currentFile.name}]\n${userMessage}`
    }

    const historyMessages = messages.slice(-6)
    const historyText = historyMessages.map(m => {
      const label = m.role === 'user' ? '用户' : '助手'
      return `【${label}】${m.content}`
    }).join('\n\n')
    const finalMessage = historyText ? `${historyText}\n\n【当前问题】${userMessage}` : userMessage

    // Add User Message immediately
    updateSessionMessages(activeSessionId, prev => [...prev, { role: 'user', content: displayContent }])
    
    setInput('')
    setSelectedFile(null)
    setLoading(true)

    try {
      let response;
      
      // Always use FormData to support both text and optional file
      const formData = new FormData()
      formData.append('message', finalMessage)
      formData.append('project_type', currentProjectType)
      if (currentFile) {
        formData.append('file', currentFile)
      }

      response = await axios.post('/api/v1/chat', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      const aiResponse = response.data.response
      const fileUrl = response.data.file_url
      const msgProjectType = response.data.project_type
      const sources = response.data.sources

      // If there was a file upload, update the LAST user message to include the fileUrl
      if (fileUrl) {
          updateSessionMessages(activeSessionId, prev => {
              const newMsgs = [...prev]
              // Find the last user message. Since we just added one and haven't added AI response yet, it should be the last one.
              const lastMsgIndex = newMsgs.length - 1
              if (lastMsgIndex >= 0 && newMsgs[lastMsgIndex].role === 'user') {
                  newMsgs[lastMsgIndex] = { ...newMsgs[lastMsgIndex], fileUrl: fileUrl }
              }
              return newMsgs
          })
      }

      updateSessionMessages(activeSessionId, prev => {
        const baseIndex = prev.length
        setStreamingIndex(baseIndex)
        setStreamingText('')
        const full = aiResponse || ''
        let i = 0
        const step = () => {
          i += 10
          setStreamingText(full.slice(0, i))
          if (i < full.length) {
            setTimeout(step, 25)
          } else {
            setStreamingIndex(null)
          }
        }
        setTimeout(step, 10)
        return [...prev, { 
          role: 'assistant', 
          content: full, 
          projectType: msgProjectType,
          sources: sources
        }]
      })
    } catch (error) {
      console.error('Error:', error)
      updateSessionMessages(activeSessionId, prev => [...prev, { 
        role: 'assistant', 
        content: `抱歉，请求失败: ${error.response?.data?.detail || error.message}`,
        projectType: currentProjectType // Keep current project type even on error
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const fetchKbFiles = useCallback(async () => {
    if (userRole !== 'admin') return
    try {
      const res = await axios.get(`/api/v1/documents?project_type=${currentProjectType}`)
      setKbFiles(res.data)
    } catch (error) {
      console.error('Failed to fetch documents:', error)
      alert('无法加载知识库文件')
    }
  }, [currentProjectType, userRole])

  useEffect(() => {
    if (userRole === 'admin' && showKbModal) {
      fetchKbFiles()
    }
  }, [showKbModal, userRole, fetchKbFiles])

  const handleLogin = async () => {
    if (!loginPassword) {
      alert('请输入密码')
      return
    }
    try {
      const res = await axios.post('/api/v1/login', { password: loginPassword })
      if (res.data.status === 'success') {
        setUserRole('admin')
        localStorage.setItem('user_role', 'admin')
        setShowLoginModal(false)
        setLoginPassword('')
        alert('管理员登录成功')
      }
    } catch (err) {
      console.error('Login failed:', err)
      alert('密码错误')
    }
  }

  const handleLogout = () => {
    setUserRole('user')
    localStorage.removeItem('user_role')
    alert('已切换回普通用户模式')
  }

  const handleKbUpload = async () => {
    if (userRole !== 'admin') return
    if (!uploadFile) {
      alert('请选择要上传的文件')
      return
    }

    setIsUploading(true)
    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('doc_type', uploadType)
    formData.append('project_type', currentProjectType)

    try {
      await axios.post('/api/v1/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      alert('上传成功')
      setUploadFile(null)
      if (kbFileInputRef.current) kbFileInputRef.current.value = ''
      fetchKbFiles()
    } catch (error) {
      console.error('Upload failed:', error)
      alert('上传失败: ' + (error.response?.data?.detail || error.message))
    } finally {
      setIsUploading(false)
    }
  }

  const handleCreateProjectType = async () => {
    if (userRole !== 'admin') return
    if (!newTypeName || !newTypeId) {
      alert('请填写完整信息')
      return
    }
    // Simple ID validation: alphanumeric and underscores only
    if (!/^[a-zA-Z0-9_]+$/.test(newTypeId)) {
        alert('项目ID只能包含字母、数字和下划线')
        return
    }

    try {
      await axios.post('/api/v1/project-types', {
        id: newTypeId,
        name: newTypeName
      })
      alert('创建成功')
      setNewTypeName('')
      setNewTypeId('')
      setShowCreateTypeModal(false)
      fetchProjectTypes()
    } catch (e) {
      console.error('Failed to create project type', e)
      alert('创建失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleGenerateId = async () => {
    if (!newTypeName) {
        alert('请先输入项目类型名称')
        return
    }
    setIsGeneratingId(true)
    try {
        const res = await axios.post('/api/v1/generate-id', { name: newTypeName })
        setNewTypeId(res.data.id)
    } catch (e) {
        console.error('Failed to generate ID', e)
        alert('自动生成ID失败，请手动输入')
    } finally {
        setIsGeneratingId(false)
    }
  }

  const handleUpdateProjectType = async () => {
    if (userRole !== 'admin') return
    if (!editTypeName) {
      alert('请填写项目名称')
      return
    }

    try {
      console.log('Updating project type:', currentProjectType, 'to', editTypeName)
      const url = `/api/v1/project-types/${encodeURIComponent(currentProjectType)}`
      await axios.put(url, {
        id: currentProjectType,
        name: editTypeName
      })
      alert('修改成功')
      setShowEditTypeModal(false)
      fetchProjectTypes()
    } catch (e) {
      console.error('Failed to update project type', e)
      alert('修改失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleDeleteProjectType = async () => {
      if (userRole !== 'admin') return
      if (currentProjectType === 'general') return
      
      const typeName = projectTypes.find(p => p.id === currentProjectType)?.name || currentProjectType
      if (!window.confirm(`确定要删除项目类型 "${typeName}" 吗？\n\n警告：\n1. 将删除该类型下的所有知识库文件。\n2. 相关的聊天记录可能无法正常显示。\n3. 此操作不可恢复。`)) {
          return
      }

      try {
          await axios.delete(`/api/v1/project-types/${currentProjectType}`)
          alert('删除成功')
          setCurrentProjectType('general')
          fetchProjectTypes()
      } catch (e) {
          console.error('Failed to delete project type', e)
          alert('删除失败: ' + (e.response?.data?.detail || e.message))
      }
  }

  const handleDeleteFile = async (file) => {
    if (userRole !== 'admin') return
    if (!window.confirm(`确定要删除文件 "${file.filename}" 吗？此操作不可恢复。`)) return

    try {
      await axios.delete(`/api/v1/documents/${file.type}/${file.filename}?project_type=${currentProjectType}`)
      setKbFiles(prev => prev.filter(f => f.filename !== file.filename))
    } catch (error) {
      console.error('Failed to delete document:', error)
      alert('删除失败')
    }
  }

  const handleDownloadFile = async (file) => {
    try {
      const url = `/api/v1/documents/${file.type}/${file.filename}/download?project_type=${currentProjectType}`
      window.open(url, '_blank')
    } catch (error) {
      console.error('Failed to download document:', error)
      alert('无法打开文件')
    }
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* API Connection Status */}
      {!apiConnected && (
        <div className="fixed top-4 right-4 z-50 bg-red-50 border border-red-200 p-3 rounded-lg shadow-lg">
          <div className="flex items-center gap-2 text-red-700 text-sm">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
            <span>后端连接失败，请检查: {API_BASE_URL}</span>
          </div>
        </div>
      )}
      
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 hidden md:flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-800">政府项目咨询</h1>
            {userRole === 'admin' ? (
              <div className="flex gap-1">
                <button 
                    type="button"
                    onClick={() => setShowCreateTypeModal(true)}
                    className="p-1 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                    title="新建项目类型"
                >
                    <PlusCircle size={20} />
                </button>
                <button 
                    onClick={handleLogout}
                    className="p-1 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                    title="退出管理员模式"
                >
                    <X size={20} />
                </button>
              </div>
            ) : (
              <button 
                  onClick={() => setShowLoginModal(true)}
                  className="text-xs text-blue-600 hover:underline"
              >
                  管理员登录
              </button>
            )}
          </div>
          <div className="mt-4">
            <label className="text-xs text-gray-500 mb-1 block">当前项目类型</label>
            <div className="flex gap-2 items-center">
                <select 
                    value={currentProjectType} 
                    onChange={(e) => setCurrentProjectType(e.target.value)}
                    className="flex-1 min-w-0 p-2 border border-gray-300 rounded text-sm bg-white"
                >
                    {projectTypes.map(pt => (
                        <option key={pt.id} value={pt.id}>{pt.name}</option>
                    ))}
                </select>
                {userRole === 'admin' && (
                  <div className="flex gap-1 flex-shrink-0">
                    <button 
                        onClick={() => {
                          const currentType = projectTypes.find(p => p.id === currentProjectType)
                          setEditTypeName(currentType?.name || '')
                          setShowEditTypeModal(true)
                        }}
                        className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded"
                        title="修改当前项目名称"
                    >
                        <Edit2 size={18} />
                    </button>
                    {currentProjectType !== 'general' && (
                        <button 
                            onClick={handleDeleteProjectType}
                            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded flex-shrink-0"
                            title="删除当前项目类型"
                        >
                            <Trash2 size={18} />
                        </button>
                    )}
                  </div>
                )}
            </div>
          </div>
        </div>
        <div className="p-4 flex-1 overflow-y-auto">
          <button 
            onClick={startNewChat}
            className="w-full flex items-center justify-center p-2 mb-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <PlusCircle size={18} className="mr-2" />
            新对话
          </button>
          <div className="text-sm text-gray-500 mb-2">历史记录</div>
          {sessions.map(session => (
            <div 
              key={session.id}
              onClick={() => setCurrentSessionId(session.id)}
              className={`p-2 rounded cursor-pointer text-sm mb-1 flex items-center justify-between group ${
                session.id === currentSessionId ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              <div className="flex items-center overflow-hidden">
                <MessageSquare size={14} className="mr-2 flex-shrink-0" />
                <span className="truncate">{session.title}</span>
              </div>
              <button
                onClick={(e) => deleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 hover:bg-red-50 rounded"
                title="删除会话"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
        
        {/* KB Management Button */}
        {userRole === 'admin' && (
          <div className="p-4 border-t border-gray-200">
            <button 
              onClick={() => setShowKbModal(true)}
              className="w-full flex items-center justify-center p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Database size={18} className="mr-2" />
              管理知识库
            </button>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, index) => {
            const getBotInfo = (m) => {
              if (m.role !== 'assistant') return null;
              const type = projectTypes.find(p => p.id === m.projectType);
              if (type) {
                return {
                  name: type.name,
                  color: m.projectType === 'general' ? 'bg-blue-600' : 'bg-green-600'
                };
              }
              return {
                name: '已删除项目',
                color: 'bg-gray-400'
              };
            };
            const botInfo = getBotInfo(msg);

            return (
              <div key={index} className={`flex w-full group ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex max-w-[80%] items-start ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                  {/* Avatar */}
                  <div 
                    className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center mx-2 ${
                      msg.role === 'user' ? 'bg-blue-600' : (botInfo?.color || 'bg-green-600')
                    }`}
                    title={msg.role === 'assistant' ? `来自项目：${botInfo?.name || '未知'}` : '您'}
                  >
                    {msg.role === 'user' ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
                  </div>
                  
                  {/* Bubble */}
                <div className={`p-3 rounded-lg text-sm whitespace-pre-wrap flex flex-col ${
                  msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-br-none' 
                    : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none shadow-sm'
                }`}>
                  {msg.content}
                  
                  {/* File Download Link */}
                  {msg.fileUrl && (
                      <a 
                        href={msg.fileUrl} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className={`mt-2 flex items-center p-2 rounded text-xs transition-colors ${
                            msg.role === 'user' 
                                ? 'bg-blue-700 hover:bg-blue-800 text-blue-100' 
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
                        }`}
                      >
                        <FileText size={14} className="mr-2" />
                        <span>打开上传的文件</span>
                        <ExternalLink size={12} className="ml-2" />
                      </a>
                  )}

                  {/* View Source Button for Assistant Messages (Admin Only) */}
                  {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && userRole === 'admin' && (
                    <button 
                      onClick={() => {
                        setActiveSources(msg.sources);
                        setShowSourceModal(true);
                      }}
                      className="mt-2 flex items-center p-2 rounded text-xs transition-colors bg-blue-50 hover:bg-blue-100 text-blue-600 border border-blue-100"
                    >
                      <Search size={14} className="mr-2" />
                      <span>查看原文依据 ({msg.sources.length})</span>
                    </button>
                  )}

                  {/* Feedback Buttons for Assistant Messages */}
                  {msg.role === 'assistant' && (
                    <div className="mt-2 flex items-center space-x-2">
                      <button 
                        onClick={() => handleFeedback('like', index, msg.content)}
                        className={`flex items-center p-1.5 rounded text-xs transition-colors ${
                          msg.feedback === 'like' 
                            ? 'bg-green-100 text-green-600 border border-green-200' 
                            : 'bg-gray-50 hover:bg-green-50 text-gray-500 hover:text-green-600 border border-gray-200'
                        }`}
                        title="点赞"
                      >
                        <ThumbsUp size={14} className={msg.feedback === 'like' ? 'fill-current' : ''} />
                      </button>
                      <button 
                        onClick={() => handleFeedback('dislike', index, msg.content)}
                        className={`flex items-center p-1.5 rounded text-xs transition-colors ${
                          msg.feedback === 'dislike' 
                            ? 'bg-red-100 text-red-600 border border-red-200' 
                            : 'bg-gray-50 hover:bg-red-50 text-gray-500 hover:text-red-600 border border-gray-200'
                        }`}
                        title="点踩"
                      >
                        <ThumbsDown size={14} className={msg.feedback === 'dislike' ? 'fill-current' : ''} />
                      </button>
                    </div>
                  )}
                </div>

                {/* Delete Button */}
                <button 
                  onClick={() => deleteMessage(index)}
                  className={`opacity-0 group-hover:opacity-100 transition-opacity p-2 text-gray-400 hover:text-red-500 self-center ${msg.role === 'user' ? 'mr-1' : 'ml-1'}`}
                  title="删除此消息"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          )
        })}
        {loading && (
            <div className="flex justify-start">
               <div className="flex flex-row">
                <div className="flex-shrink-0 h-8 w-8 rounded-full bg-green-600 flex items-center justify-center mx-2">
                  <Bot size={16} className="text-white" />
                </div>
                <div className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm flex items-center">
                  <Loader2 size={16} className="animate-spin text-gray-500 mr-2" />
                  <span className="text-sm text-gray-500">思考中...</span>
                </div>
               </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-gray-200">
          <div className="max-w-4xl mx-auto">
            {/* File Preview Chip */}
            {selectedFile && (
              <div className="mb-2 flex items-center inline-flex bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm border border-blue-100">
                <FileText size={14} className="mr-2" />
                <span className="max-w-xs truncate">{selectedFile.name}</span>
                <button 
                  onClick={removeSelectedFile}
                  className="ml-2 p-0.5 hover:bg-blue-100 rounded-full text-blue-500"
                >
                  <X size={14} />
                </button>
              </div>
            )}
            
            <div className="flex items-center space-x-2">
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-full transition-colors"
                title="上传文件"
              >
                <Paperclip size={20} />
              </button>
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileSelect} 
                className="hidden" 
                accept=".pdf,.doc,.docx,.txt,.md,.xlsx,.xls,.png,.jpg,.jpeg"
              />
              
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入您的问题..."
                className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-12 py-3"
              />
              
              <button 
                onClick={sendMessage}
                disabled={(!input.trim() && !selectedFile) || loading}
                className={`p-2 rounded-full transition-colors ${
                  (!input.trim() && !selectedFile) || loading
                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                <Send size={20} />
              </button>
            </div>
            <div className="text-xs text-gray-400 mt-2 text-center">
              支持上传 PDF, Word, 图片类型文件的辅助咨询。上传PDF文件建议不超过30页，该类型文件基于本地OCR工具，识别较慢，请耐心等待。
            </div>
          </div>
        </div>
      </div>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-[350px]">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold">管理员登录</h2>
                    <button onClick={() => setShowLoginModal(false)} className="text-gray-500 hover:text-gray-700">
                        <X size={24} />
                    </button>
                </div>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">管理密码</label>
                        <input 
                            type="password" 
                            value={loginPassword}
                            onChange={(e) => setLoginPassword(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleLogin() }}
                            placeholder="请输入后台设置的密码"
                            className="w-full p-2 border border-gray-300 rounded"
                            autoFocus
                        />
                    </div>
                    <button 
                        onClick={handleLogin}
                        className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
                    >
                        登录
                    </button>
                </div>
            </div>
        </div>
      )}

      {/* Edit Project Type Modal */}
      {showEditTypeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-[400px]">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold">修改项目类型</h2>
                    <button onClick={() => setShowEditTypeModal(false)} className="text-gray-500 hover:text-gray-700">
                        <X size={24} />
                    </button>
                </div>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目类型名称</label>
                        <input 
                            type="text" 
                            value={editTypeName}
                            onChange={(e) => setEditTypeName(e.target.value)}
                            placeholder="请输入新的项目名称"
                            className="w-full p-2 border border-gray-300 rounded"
                            autoFocus
                        />
                    </div>
                    <button 
                        onClick={handleUpdateProjectType}
                        className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
                    >
                        保存修改
                    </button>
                </div>
            </div>
        </div>
      )}

      {/* Create Project Type Modal */}
      {showCreateTypeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-[400px]">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold">新建项目类型</h2>
                    <button onClick={() => setShowCreateTypeModal(false)} className="text-gray-500 hover:text-gray-700">
                        <X size={24} />
                    </button>
                </div>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目类型名称</label>
                        <input 
                            type="text" 
                            value={newTypeName}
                            onChange={(e) => setNewTypeName(e.target.value)}
                            placeholder="例如：人工智能专项"
                            className="w-full p-2 border border-gray-300 rounded"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目类型ID (英文)</label>
                        <div className="flex gap-2">
                            <input 
                                type="text" 
                                value={newTypeId}
                                onChange={(e) => setNewTypeId(e.target.value)}
                                placeholder="例如：ai_special"
                                className="flex-1 p-2 border border-gray-300 rounded"
                            />
                            <button
                                onClick={handleGenerateId}
                                disabled={isGeneratingId || !newTypeName}
                                className={`px-3 py-2 rounded text-sm whitespace-nowrap border ${
                                    isGeneratingId || !newTypeName
                                    ? 'bg-gray-100 text-gray-400 border-gray-200'
                                    : 'bg-white text-blue-600 border-blue-200 hover:bg-blue-50'
                                }`}
                                title="根据名称自动翻译生成ID"
                            >
                                {isGeneratingId ? <Loader2 size={16} className="animate-spin" /> : '自动生成'}
                            </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">只能包含字母、数字和下划线</p>
                    </div>
                    <button 
                        onClick={handleCreateProjectType}
                        className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
                    >
                        创建
                    </button>
                </div>
            </div>
        </div>
      )}

      {/* KB Management Modal */}
      {showKbModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-[800px] max-h-[80vh] flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">知识库管理 - {projectTypes.find(p => p.id === currentProjectType)?.name}</h2>
              <button onClick={() => setShowKbModal(false)} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>

            {/* Upload Section */}
            <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <h3 className="text-sm font-semibold mb-2">上传新文件</h3>
                <div className="flex items-center gap-4">
                    <input 
                        type="file" 
                        ref={kbFileInputRef}
                        onChange={(e) => setUploadFile(e.target.files[0])}
                        className="block w-full text-sm text-gray-500
                            file:mr-4 file:py-2 file:px-4
                            file:rounded-full file:border-0
                            file:text-sm file:font-semibold
                            file:bg-blue-50 file:text-blue-700
                            hover:file:bg-blue-100"
                        accept=".pdf,.docx,.txt,.md,.xlsx,.xls,.html,.htm"
                    />
                    <select 
                        value={uploadType} 
                        onChange={(e) => setUploadType(e.target.value)}
                        className="p-2 border border-gray-300 rounded text-sm"
                    >
                        <option value="policy">规章制度</option>
                        <option value="case">典型案例</option>
                    </select>
                    <button 
                        onClick={handleKbUpload}
                        disabled={isUploading || !uploadFile}
                        className={`px-4 py-2 rounded text-white text-sm whitespace-nowrap ${
                            isUploading || !uploadFile 
                            ? 'bg-blue-300 cursor-not-allowed' 
                            : 'bg-blue-600 hover:bg-blue-700'
                        }`}
                    >
                        {isUploading ? '上传中...' : '上传'}
                    </button>
                </div>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">文件名</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">类型</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {kbFiles.map((file, idx) => (
                    <tr key={idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 flex items-center">
                        <FileText size={16} className="mr-2 text-gray-400" />
                        {file.filename}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          file.type === 'policy' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                        }`}>
                          {file.type === 'policy' ? '规章制度' : '典型案例'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button 
                          onClick={() => handleDownloadFile(file)}
                          className="text-blue-600 hover:text-blue-900 mr-4"
                          title="下载/预览"
                        >
                          <Download size={16} />
                        </button>
                        <button 
                          onClick={() => handleDeleteFile(file)}
                          className="text-red-600 hover:text-red-900"
                          title="删除"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {kbFiles.length === 0 && (
                    <tr>
                      <td colSpan="3" className="px-6 py-10 text-center text-gray-500">
                        暂无文件，请手动将文件放入 backend/data/policies 或 backend/data/cases 目录
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-200 text-right">
              <button 
                onClick={() => setShowKbModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Source Modal */}
      {showSourceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50 rounded-t-xl">
              <div className="flex items-center space-x-2">
                <Search size={20} className="text-blue-600" />
                <h3 className="text-lg font-bold text-gray-800">原文依据核对</h3>
              </div>
              <button 
                onClick={() => setShowSourceModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gray-50">
              {activeSources.map((source, idx) => (
                <div key={idx} className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                  <div className="px-4 py-2 bg-gray-100 border-b border-gray-200 flex justify-between items-center">
                    <span className="text-sm font-semibold text-gray-700 flex items-center">
                      <FileText size={14} className="mr-2 text-blue-500" />
                      依据 {idx + 1}: {source.filename}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      source.type === 'policy' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                    }`}>
                      {source.type === 'policy' ? '规章制度' : '典型案例'}
                    </span>
                  </div>
                  <div className="p-4">
                    <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded border border-gray-100">
                      {source.content}
                    </div>
                    <div className="mt-3 flex justify-end">
                      <button 
                        onClick={() => {
                          // Simple download logic using existing endpoint
                          window.open(`/api/v1/documents/${source.type}/${encodeURIComponent(source.filename)}/download?project_type=${currentProjectType}`, '_blank');
                        }}
                        className="flex items-center text-xs text-blue-600 hover:text-blue-800 font-medium"
                      >
                        <Download size={14} className="mr-1" />
                        下载完整文件核对
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {activeSources.length === 0 && (
                <div className="text-center py-20 text-gray-500">
                  未找到相关原文依据
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-gray-200 bg-white rounded-b-xl text-right">
              <button 
                onClick={() => setShowSourceModal(false)}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-md"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
