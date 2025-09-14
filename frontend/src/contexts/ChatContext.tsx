import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  result?: any;
  settings?: {
    resultCount: string;
    contentType: string;
    modelType: string;
  };
  collapsed?: boolean;
}

interface ChatContextType {
  chatHistory: ChatMessage[];
  setChatHistory: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  toggleMessageCollapse: (messageId: string) => void;
  clearChat: () => void;
  exportChatHistory: () => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};

interface ChatProviderProps {
  children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  const addMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date(),
      collapsed: false // Default to expanded
    };
    setChatHistory(prev => [...prev, newMessage]);
  };

  const toggleMessageCollapse = (messageId: string) => {
    setChatHistory(prev => 
      prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, collapsed: !msg.collapsed }
          : msg
      )
    );
  };

  const clearChat = () => {
    setChatHistory([]);
  };

  const exportChatHistory = () => {
    if (chatHistory.length === 0) {
      alert('No chat history to export');
      return;
    }

    // Group messages into triplets (user query, settings, assistant response)
    const triplets: Array<{
      query: string;
      settings: any;
      results: any;
    }> = [];

    for (let i = 0; i < chatHistory.length; i += 2) {
      const userMessage = chatHistory[i];
      const assistantMessage = chatHistory[i + 1];

      if (userMessage && userMessage.type === 'user' && assistantMessage && assistantMessage.type === 'assistant') {
        triplets.push({
          query: userMessage.content,
          settings: assistantMessage.settings || null,
          results: assistantMessage.result || null
        });
      }
    }

    // Create filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `bible-search-chat-${timestamp}.json`;

    // Create and download the file
    const dataStr = JSON.stringify(triplets, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  const value: ChatContextType = {
    chatHistory,
    setChatHistory,
    addMessage,
    toggleMessageCollapse,
    clearChat,
    exportChatHistory
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};
