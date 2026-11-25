import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

export const MainLayout: React.FC = () => {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-secondary dark:bg-slate-950">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-surface-secondary dark:bg-slate-950 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
