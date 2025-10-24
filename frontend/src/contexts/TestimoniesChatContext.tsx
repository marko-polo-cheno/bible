import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  result?: any;
  collapsed?: boolean;
}

interface TestimoniesChatContextType {
  chatHistory: ChatMessage[];
  setChatHistory: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  toggleMessageCollapse: (messageId: string) => void;
  clearChat: () => void;
  exportChatHistory: () => void;
}

const TestimoniesChatContext = createContext<TestimoniesChatContextType | undefined>(undefined);

export const useTestimoniesChat = () => {
  const context = useContext(TestimoniesChatContext);
  if (context === undefined) {
    throw new Error('useTestimoniesChat must be used within a TestimoniesChatProvider');
  }
  return context;
};

interface TestimoniesChatProviderProps {
  children: ReactNode;
}

export const TestimoniesChatProvider: React.FC<TestimoniesChatProviderProps> = ({ children }) => {
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  const addMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date(),
      collapsed: false
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

    const triplets: Array<{
      query: string;
      results: any;
    }> = [];

    for (let i = 0; i < chatHistory.length; i += 2) {
      const userMessage = chatHistory[i];
      const assistantMessage = chatHistory[i + 1];

      if (userMessage && userMessage.type === 'user' && assistantMessage && assistantMessage.type === 'assistant') {
        triplets.push({
          query: userMessage.content,
          results: assistantMessage.result || null
        });
      }
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `testimonies-search-chat-${timestamp}.json`;

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

  const value: TestimoniesChatContextType = {
    chatHistory,
    setChatHistory,
    addMessage,
    toggleMessageCollapse,
    clearChat,
    exportChatHistory
  };

  return (
    <TestimoniesChatContext.Provider value={value}>
      {children}
    </TestimoniesChatContext.Provider>
  );
};
