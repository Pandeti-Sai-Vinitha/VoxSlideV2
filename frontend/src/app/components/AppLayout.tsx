import { Outlet, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  Library,
  MessageSquare,
  LogOut,
  Presentation
} from 'lucide-react';
import { Button } from './ui/button';

interface AppLayoutProps {
  onLogout: () => void;
}

export default function AppLayout({ onLogout }: AppLayoutProps) {
  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/upload', icon: Upload, label: 'Generate Slides' },
    { to: '/library', icon: Library, label: 'Slide Library' },
    { to: '/settings', icon: MessageSquare, label: 'Interactive Workspace' }
  ];

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/30">
      <aside className="w-64 bg-white/70 backdrop-blur-md border-r border-indigo-100 flex flex-col shadow-lg">
        <div className="p-6 bg-gradient-to-br from-indigo-50 to-purple-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-xl flex items-center justify-center shadow-md">
              <Presentation className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">SlidesFlix</h1>
              <p className="text-xs text-slate-600">AI Platform</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-all focus:outline-none focus-visible:outline-none focus-visible:ring-0 ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md'
                    : 'text-slate-600 hover:bg-indigo-50 hover:text-indigo-700'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.description ? (
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-semibold block">{item.label}</span>
                  <span className="text-[10px] opacity-70 font-normal leading-tight">
                    {item.description}
                  </span>
                </div>
              ) : (
                <span className="text-sm font-medium">{item.label}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-indigo-100">
          <Button
            variant="ghost"
            className="w-full justify-start text-slate-600 hover:text-indigo-700 hover:bg-indigo-50"
            onClick={onLogout}
          >
            <LogOut className="w-5 h-5 mr-3" />
            Logout
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
