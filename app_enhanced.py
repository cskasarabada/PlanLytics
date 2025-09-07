import React, { useState, useEffect, useCallback } from 'react';
import { Upload, FileText, Brain, Download, Loader2, CheckCircle, AlertCircle, User, BarChart3, Settings, LogOut, Clock, TrendingUp } from 'lucide-react';

const SaaSFileAnalysisPlatform = () => {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken'));
  const [userDashboard, setUserDashboard] = useState(null);

  // Authentication state
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ 
    email: '', 
    password: '', 
    company: '',
    firstName: '',
    lastName: ''
  });

  // Analysis configuration
  const [analysisConfig, setAnalysisConfig] = useState({
    template: 'master',
    approach: 'comprehensive',
    ai_provider: 'auto',
    priority: 'normal',
    custom_instructions: ''
  });

    # In app_enhanced.py - update CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://icm-planlytics.com",
            "https://www.icm-planlytics.com", 
            "http://localhost:3000",  # for local testing
            "*"  # Remove this in production for security
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
  const templates = [
    { value: 'master', label: 'Master Analysis', description: 'Comprehensive analysis of all plan components' },
    { value: 'risk_assessment', label: 'Risk Assessment', description: 'Focus on compliance and operational risks' },
    { value: 'oracle_mapping', label: 'Oracle ICM Mapping', description: 'Technical mapping to Oracle ICM objects' },
    { value: 'quick_analysis', label: 'Quick Analysis', description: 'Fast overview with key insights' },
    { value: 'automation_framework', label: 'Automation Framework', description: 'Automation readiness assessment' }
  ];

  const approaches = [
    { value: 'comprehensive', label: 'Comprehensive', description: 'All AI agents for complete analysis' },
    { value: 'quick_scan', label: 'Quick Scan', description: 'Essential insights only' },
    { value: 'risk_focused', label: 'Risk Focused', description: 'Compliance and risk assessment' },
    { value: 'technical_mapping', label: 'Technical Mapping', description: 'Oracle ICM implementation focus' }
  ];

  const aiProviders = [
    { value: 'auto', label: 'Auto Select', description: 'Best model for the task' },
    { value: 'openai', label: 'OpenAI GPT-4', description: 'Latest GPT-4 model' },
    { value: 'anthropic', label: 'Claude 3 Sonnet', description: 'Anthropic Claude' },
    { value: 'azure', label: 'Azure OpenAI', description: 'Enterprise OpenAI' }
  ];

  // API calls
  const apiCall = async (endpoint, options = {}) => {
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(authToken && { 'Authorization': `Bearer ${authToken}` }),
        ...options.headers
      },
      ...options
    };

    const response = await fetch(`/api${endpoint}`, config);
    
    if (response.status === 401) {
      setAuthToken(null);
      localStorage.removeItem('authToken');
      setCurrentUser(null);
      return null;
    }
    
    return response;
  };

  // Authentication functions
  const login = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setAuthToken(data.access_token);
        localStorage.setItem('authToken', data.access_token);
        await loadUserData();
      } else {
        alert(data.detail || 'Login failed');
      }
    } catch (error) {
      alert('Login error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const register = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(registerForm)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setAuthToken(data.access_token);
        localStorage.setItem('authToken', data.access_token);
        await loadUserData();
      } else {
        alert(data.detail || 'Registration failed');
      }
    } catch (error) {
      alert('Registration error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setAuthToken(null);
    localStorage.removeItem('authToken');
    setCurrentUser(null);
    setUserDashboard(null);
    setActiveTab('upload');
  };

  const loadUserData = async () => {
    try {
      const response = await apiCall('/user/dashboard');
      if (response && response.ok) {
        const data = await response.json();
        setCurrentUser(data.user);
        setUserDashboard(data);
        setAnalyses(data.recent_analyses || []);
      }
    } catch (error) {
      console.error('Error loading user data:', error);
    }
  };

  // File upload handler
  const handleFileUpload = useCallback((event) => {
    const file = event.target.files[0];
    if (file) {
      setUploadedFile(file);
    }
  }, []);

  // Enhanced analysis submission
  const submitAnalysis = async () => {
    if (!uploadedFile) {
      alert('Please select a file first');
      return;
    }

    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      formData.append('request_data', JSON.stringify(analysisConfig));

      const response = await fetch('/analyze/enhanced', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        body: formData
      });

      const result = await response.json();
      
      if (response.ok) {
        // Add to analyses list
        setAnalyses(prev => [result, ...prev]);
        
        // Clear form
        setUploadedFile(null);
        document.querySelector('input[type="file"]').value = '';
        
        // Switch to results tab
        setActiveTab('results');
        
        // Poll for completion if processing
        if (result.status === 'processing') {
          pollAnalysisStatus(result.analysis_id);
        }
      } else {
        alert(result.detail || 'Analysis failed');
      }
    } catch (error) {
      alert('Analysis error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Poll for analysis completion
  const pollAnalysisStatus = async (analysisId) => {
    const poll = async () => {
      try {
        const response = await apiCall(`/analyze/${analysisId}/status`);
        if (response && response.ok) {
          const data = await response.json();
          
          // Update analysis in list
          setAnalyses(prev => prev.map(a => 
            a.analysis_id === analysisId ? { ...a, ...data } : a
          ));
          
          if (data.status === 'completed' || data.status === 'failed') {
            return; // Stop polling
          }
          
          // Continue polling
          setTimeout(poll, 5000);
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    };
    
    setTimeout(poll, 5000);
  };

  // Load user data on auth token change
  useEffect(() => {
    if (authToken) {
      loadUserData();
    }
  }, [authToken]);

  // Render authentication forms
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              AI Compensation Platform
            </h1>
            <p className="text-gray-600">Enterprise compensation plan analysis</p>
          </div>

          <div className="flex mb-6">
            <button
              onClick={() => setActiveTab('login')}
              className={`flex-1 py-2 px-4 text-center ${
                activeTab === 'login' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-700'
              } rounded-l-lg transition-colors`}
            >
              Login
            </button>
            <button
              onClick={() => setActiveTab('register')}
              className={`flex-1 py-2 px-4 text-center ${
                activeTab === 'register' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-700'
              } rounded-r-lg transition-colors`}
            >
              Register
            </button>
          </div>

          {activeTab === 'login' ? (
            <form onSubmit={login} className="space-y-4">
              <input
                type="email"
                placeholder="Email"
                value={loginForm.email}
                onChange={(e) => setLoginForm(prev => ({ ...prev, email: e.target.value }))}
                className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={loginForm.password}
                onChange={(e) => setLoginForm(prev => ({ ...prev, password: e.target.value }))}
                className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-500 text-white py-3 rounded-lg hover:bg-blue-600 disabled:opacity-50"
              >
                {loading ? <Loader2 className="animate-spin mx-auto" size={20} /> : 'Login'}
              </button>
            </form>
          ) : (
            <form onSubmit={register} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <input
                  type="text"
                  placeholder="First Name"
                  value={registerForm.firstName}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, firstName: e.target.value }))}
                  className="p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="text"
                  placeholder="Last Name"
                  value={registerForm.lastName}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, lastName: e.target.value }))}
                  className="p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <input
                type="email"
                placeholder="Email"
                value={registerForm.email}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, email: e.target.value }))}
                className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="text"
                placeholder="Company"
                value={registerForm.company}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, company: e.target.value }))}
                className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="password"
                placeholder="Password (min 8 chars)"
                value={registerForm.password}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, password: e.target.value }))}
                className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                minLength={8}
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-green-500 text-white py-3 rounded-lg hover:bg-green-600 disabled:opacity-50"
              >
                {loading ? <Loader2 className="animate-spin mx-auto" size={20} /> : 'Register'}
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  // Main application interface
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-semibold text-gray-900">
                AI Compensation Platform
              </h1>
              <span className="text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded">
                {currentUser?.subscription_tier?.toUpperCase()}
              </span>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-600">
                API: {currentUser?.api_calls_count || 0}/{currentUser?.api_calls_limit || 0}
              </div>
              <div className="flex items-center space-x-2 text-sm text-gray-700">
                <User size={16} />
                <span>{currentUser?.email}</span>
              </div>
              <button
                onClick={logout}
                className="flex items-center space-x-1 text-gray-600 hover:text-gray-900"
              >
                <LogOut size={16} />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation Tabs */}
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg mb-8">
          {[
            { id: 'upload', label: 'New Analysis', icon: Upload },
            { id: 'results', label: 'Results', icon: FileText },
            { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
            { id: 'settings', label: 'Settings', icon: Settings }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex-1 flex items-center justify-center space-x-2 py-2 px-4 rounded-md transition-colors ${
                activeTab === id
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'upload' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-2xl font-semibold mb-6">Upload & Analyze Document</h2>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* File Upload */}
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Document
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                    <div className="mt-4">
                      <input
                        type="file"
                        onChange={handleFileUpload}
                        accept=".pdf,.docx,.txt,.csv,.xlsx"
                        className="hidden"
                        id="file-upload"
                      />
                      <label
                        htmlFor="file-upload"
                        className="cursor-pointer bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600 transition-colors"
                      >
                        Choose File
                      </label>
                    </div>
                    <p className="mt-2 text-sm text-gray-500">
                      PDF, DOCX, TXT, CSV, XLSX up to 100MB
                    </p>
                  </div>
                  
                  {uploadedFile && (
                    <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
                      <div className="flex items-center space-x-2">
                        <CheckCircle className="text-green-500" size={16} />
                        <span className="text-sm text-green-700">
                          {uploadedFile.name} ({(uploadedFile.size / 1024 / 1024).toFixed(2)} MB)
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Analysis Configuration */}
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Analysis Template
                  </label>
                  <select
                    value={analysisConfig.template}
                    onChange={(e) => setAnalysisConfig(prev => ({ ...prev, template: e.target.value }))}
                    className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {templates.map(template => (
                      <option key={template.value} value={template.value}>
                        {template.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-sm text-gray-500">
                    {templates.find(t => t.value === analysisConfig.template)?.description}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Analysis Approach
                  </label>
                  <select
                    value={analysisConfig.approach}
                    onChange={(e) => setAnalysisConfig(prev => ({ ...prev, approach: e.target.value }))}
                    className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {approaches.map(approach => (
                      <option key={approach.value} value={approach.value}>
                        {approach.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-sm text-gray-500">
                    {approaches.find(a => a.value === analysisConfig.approach)?.description}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    AI Provider
                  </label>
                  <select
                    value={analysisConfig.ai_provider}
                    onChange={(e) => setAnalysisConfig(prev => ({ ...prev, ai_provider: e.target.value }))}
                    className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {aiProviders.map(provider => (
                      <option key={provider.value} value={provider.value}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-sm text-gray-500">
                    {aiProviders.find(p => p.value === analysisConfig.ai_provider)?.description}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Priority
                  </label>
                  <select
                    value={analysisConfig.priority}
                    onChange={(e) => setAnalysisConfig(prev => ({ ...prev, priority: e.target.value }))}
                    className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="normal">Normal (5-10 min)</option>
                    <option value="high">High Priority (1-3 min)</option>
                    <option value="urgent">Urgent (immediate)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Custom Instructions (Optional)
                  </label>
                  <textarea
                    value={analysisConfig.custom_instructions}
                    onChange={(e) => setAnalysisConfig(prev => ({ ...prev, custom_instructions: e.target.value }))}
                    placeholder="Any specific areas to focus on or requirements..."
                    rows={3}
                    className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <button
                  onClick={submitAnalysis}
                  disabled={!uploadedFile || loading}
                  className="w-full bg-blue-500 text-white py-3 px-4 rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      <span>Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <Brain size={20} />
                      <span>Start Analysis</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'results' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-2xl font-semibold mb-6">Analysis Results</h2>
              
              {analyses.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-4 text-lg font-medium text-gray-900">No analyses yet</h3>
                  <p className="mt-2 text-gray-500">Upload a document to get started</p>
                  <button
                    onClick={() => setActiveTab('upload')}
                    className="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600"
                  >
                    Upload Document
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {analyses.map((analysis) => (
                    <div key={analysis.analysis_id} className="border border-gray-200 rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h3 className="text-lg font-medium text-gray-900">
                            {analysis.file_name || 'Analysis'}
                          </h3>
                          <p className="text-sm text-gray-500">
                            {analysis.template} • {new Date(analysis.created_at).toLocaleString()}
                          </p>
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          {analysis.status === 'completed' && (
                            <CheckCircle className="text-green-500" size={20} />
                          )}
                          {analysis.status === 'processing' && (
                            <Loader2 className="text-blue-500 animate-spin" size={20} />
                          )}
                          {analysis.status === 'failed' && (
                            <AlertCircle className="text-red-500" size={20} />
                          )}
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            analysis.status === 'completed' ? 'bg-green-100 text-green-800' :
                            analysis.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                            analysis.status === 'failed' ? 'bg-red-100 text-red-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {analysis.status}
                          </span>
                        </div>
                      </div>

                      {analysis.status === 'processing' && (
                        <div className="mb-4">
                          <div className="flex items-center space-x-2 text-sm text-gray-600">
                            <Clock size={16} />
                            <span>
                              Estimated completion: {
                                analysis.estimated_completion 
                                  ? new Date(analysis.estimated_completion).toLocaleTimeString()
                                  : 'Calculating...'
                              }
                            </span>
                          </div>
                          {analysis.progress_percentage && (
                            <div className="mt-2">
                              <div className="bg-gray-200 rounded-full h-2">
                                <div 
                                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                                  style={{ width: `${analysis.progress_percentage}%` }}
                                ></div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {analysis.status === 'completed' && (
                        <div className="space-y-4">
                          {/* Download Links */}
                          <div className="flex space-x-4">
                            {analysis.excel_url && (
                              <a
                                href={analysis.excel_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center space-x-2 bg-green-500 text-white px-4 py-2 rounded-md hover:bg-green-600"
                              >
                                <Download size={16} />
                                <span>Excel Report</span>
                              </a>
                            )}
                            {analysis.pdf_url && (
                              <a
                                href={analysis.pdf_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center space-x-2 bg-red-500 text-white px-4 py-2 rounded-md hover:bg-red-600"
                              >
                                <Download size={16} />
                                <span>PDF Report</span>
                              </a>
                            )}
                            {analysis.json_url && (
                              <a
                                href={analysis.json_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center space-x-2 bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600"
                              >
                                <Download size={16} />
                                <span>JSON Data</span>
                              </a>
                            )}
                          </div>

                          {/* Quick Insights */}
                          {analysis.results && (
                            <div className="bg-gray-50 rounded-md p-4">
                              <h4 className="font-medium text-gray-900 mb-2">Quick Insights</h4>
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                                <div>
                                  <span className="text-gray-600">Confidence Score:</span>
                                  <span className="ml-2 font-medium">
                                    {analysis.confidence_score ? `${(analysis.confidence_score * 100).toFixed(1)}%` : 'N/A'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-600">Processing Time:</span>
                                  <span className="ml-2 font-medium">
                                    {analysis.processing_time ? `${analysis.processing_time.toFixed(1)}s` : 'N/A'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-600">AI Provider:</span>
                                  <span className="ml-2 font-medium">
                                    {analysis.ai_provider_used || 'Auto'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {analysis.status === 'failed' && (
                        <div className="bg-red-50 border border-red-200 rounded-md p-4">
                          <p className="text-red-800 text-sm">
                            Analysis failed. Please try again or contact support if the issue persists.
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && userDashboard && (
          <div className="space-y-6">
            {/* Usage Overview */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center">
                  <div className="p-2 bg-blue-100 rounded-md">
                    <BarChart3 className="text-blue-600" size={24} />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm text-gray-600">API Calls</p>
                    <p className="text-2xl font-semibold">
                      {currentUser.api_calls_count}/{currentUser.api_calls_limit}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center">
                  <div className="p-2 bg-green-100 rounded-md">
                    <CheckCircle className="text-green-600" size={24} />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm text-gray-600">Completed</p>
                    <p className="text-2xl font-semibold">
                      {userDashboard.usage_stats?.successful_analyses || 0}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center">
                  <div className="p-2 bg-yellow-100 rounded-md">
                    <Clock className="text-yellow-600" size={24} />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm text-gray-600">Avg Time</p>
                    <p className="text-2xl font-semibold">
                      {userDashboard.usage_stats?.avg_processing_time 
                        ? `${userDashboard.usage_stats.avg_processing_time.toFixed(1)}s`
                        : 'N/A'
                      }
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center">
                  <div className="p-2 bg-purple-100 rounded-md">
                    <TrendingUp className="text-purple-600" size={24} />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm text-gray-600">Success Rate</p>
                    <p className="text-2xl font-semibold">
                      {userDashboard.usage_stats?.total_analyses > 0
                        ? `${((userDashboard.usage_stats.successful_analyses / userDashboard.usage_stats.total_analyses) * 100).toFixed(1)}%`
                        : 'N/A'
                      }
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
              {userDashboard.recent_analyses?.length > 0 ? (
                <div className="space-y-3">
                  {userDashboard.recent_analyses.slice(0, 5).map((analysis) => (
                    <div key={analysis.analysis_id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                      <div>
                        <p className="font-medium">{analysis.file_name}</p>
                        <p className="text-sm text-gray-500">
                          {analysis.template} • {new Date(analysis.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        analysis.status === 'completed' ? 'bg-green-100 text-green-800' :
                        analysis.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                        analysis.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {analysis.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">No recent activity</p>
              )}
            </div>

            {/* Account Info */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold mb-4">Account Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Subscription</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-gray-600">Plan:</span>
                      <span className="ml-2 font-medium">{currentUser.subscription_tier.toUpperCase()}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">API Limit:</span>
                      <span className="ml-2 font-medium">{currentUser.api_calls_limit}/month</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Member Since:</span>
                      <span className="ml-2 font-medium">
                        {new Date(currentUser.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Usage</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-gray-600">API Calls Used:</span>
                      <span className="ml-2 font-medium">
                        {currentUser.api_calls_count} ({((currentUser.api_calls_count / currentUser.api_calls_limit) * 100).toFixed(1)}%)
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${(currentUser.api_calls_count / currentUser.api_calls_limit) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-2xl font-semibold mb-6">Settings</h2>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium mb-4">Account Settings</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Email
                    </label>
                    <input
                      type="email"
                      value={currentUser?.email || ''}
                      disabled
                      className="w-full p-3 border border-gray-300 rounded-md bg-gray-50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Company
                    </label>
                    <input
                      type="text"
                      value={currentUser?.company || ''}
                      disabled
                      className="w-full p-3 border border-gray-300 rounded-md bg-gray-50"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-medium mb-4">Default Analysis Settings</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Default Template
                    </label>
                    <select className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                      {templates.map(template => (
                        <option key={template.value} value={template.value}>
                          {template.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Default AI Provider
                    </label>
                    <select className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                      {aiProviders.map(provider => (
                        <option key={provider.value} value={provider.value}>
                          {provider.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-gray-200">
                <button className="bg-blue-500 text-white px-6 py-2 rounded-md hover:bg-blue-600">
                  Save Settings
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SaaSFileAnalysisPlatform;
["python", "app_enhanced.py"]
