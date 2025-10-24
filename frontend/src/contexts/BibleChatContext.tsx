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

interface BibleChatContextType {
  chatHistory: ChatMessage[];
  setChatHistory: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  toggleMessageCollapse: (messageId: string) => void;
  clearChat: () => void;
  exportChatHistory: () => void;
}

const BibleChatContext = createContext<BibleChatContextType | undefined>(undefined);

export const useBibleChat = () => {
  const context = useContext(BibleChatContext);
  if (context === undefined) {
    throw new Error('useBibleChat must be used within a BibleChatProvider');
  }
  return context;
};

interface BibleChatProviderProps {
  children: ReactNode;
}

export const BibleChatProvider: React.FC<BibleChatProviderProps> = ({ children }) => {
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  const addMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    console.log('BibleChatContext - addMessage called with:', message);
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString(),
      timestamp: new Date(),
      collapsed: false
    };
    console.log('BibleChatContext - newMessage created:', newMessage);
    setChatHistory(prev => {
      const updated = [...prev, newMessage];
      console.log('BibleChatContext - chatHistory updated:', updated);
      return updated;
    });
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

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `bible-search-chat-${timestamp}.json`;

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

  const value: BibleChatContextType = {
    chatHistory,
    setChatHistory,
    addMessage,
    toggleMessageCollapse,
    clearChat,
    exportChatHistory
  };

  return (
    <BibleChatContext.Provider value={value}>
      {children}
    </BibleChatContext.Provider>
  );
};
