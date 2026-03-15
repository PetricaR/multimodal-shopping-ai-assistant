import React from 'react';
import { AgentState } from '../types';

interface VisualizerProps {
  state: AgentState;
}

export const Visualizer: React.FC<VisualizerProps> = ({ state }) => {
  const getStatusText = () => {
    switch (state) {
      case AgentState.DISCONNECTED: return 'OFFLINE';
      case AgentState.CONNECTING: return 'CONNECTING...';
      case AgentState.LISTENING: return 'LISTENING';
      case AgentState.THINKING: return 'THINKING...';
      case AgentState.SPEAKING: return 'SPEAKING';
      default: return 'IDLE';
    }
  };

  const getStyle = () => {
    switch (state) {
      case AgentState.DISCONNECTED:
        return { ring: 'border-white/10', bg: 'bg-slate-800', icon: '💤', glow: '' };
      case AgentState.CONNECTING:
        return { ring: 'border-yellow-500/50', bg: 'bg-yellow-500/10', icon: '⏳', glow: 'shadow-[0_0_20px_rgba(234,179,8,0.15)]' };
      case AgentState.LISTENING:
        return { ring: 'border-blue-500/50 animate-pulse', bg: 'bg-blue-500/10', icon: '🎤', glow: 'shadow-[0_0_25px_rgba(59,130,246,0.2)]' };
      case AgentState.THINKING:
        return { ring: 'border-purple-500/50', bg: 'bg-purple-500/10', icon: '🧠', glow: 'shadow-[0_0_25px_rgba(168,85,247,0.2)]' };
      case AgentState.SPEAKING:
        return { ring: 'border-emerald-500/50', bg: 'bg-emerald-500/10', icon: '👨‍🍳', glow: 'shadow-[0_0_25px_rgba(16,185,129,0.2)]' };
      default:
        return { ring: 'border-white/10', bg: 'bg-slate-800', icon: '💤', glow: '' };
    }
  };

  const s = getStyle();

  return (
    <div className="flex items-center gap-3">
      <div className={`relative w-10 h-10 rounded-full border-2 ${s.ring} ${s.bg} ${s.glow} flex items-center justify-center transition-all duration-500`}>
        <span className="text-lg">{s.icon}</span>
      </div>
      <div className="flex flex-col">
        <span className="text-[9px] text-gray-400 uppercase tracking-[0.2em] font-medium">{getStatusText()}</span>
        <div className="flex gap-0.5 mt-0.5">
          {[1, 2, 3].map(i => (
            <div key={i} className={`w-1 h-1 rounded-full ${state !== AgentState.DISCONNECTED ? 'bg-blue-500 animate-bounce' : 'bg-gray-700'}`} style={{ animationDelay: `${i * 0.15}s` }}></div>
          ))}
        </div>
      </div>
    </div>
  );
};
