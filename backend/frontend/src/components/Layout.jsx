import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard,
  CloudUpload,
  Description,
  People,
  Security,
  Person,
  Logout,
  Shield,
  Business,
  Analytics,
  Assessment,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const DRAWER_WIDTH = 260;

const navItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/dashboard' },
  { text: 'Analytics', icon: <Analytics />, path: '/analytics' },
  { text: 'AI Risk Analytics', icon: <Assessment />, path: '/ml-analytics' },
  { text: 'Upload Report', icon: <CloudUpload />, path: '/upload' },
  { text: 'Reports', icon: <Description />, path: '/reports' },
  { text: 'User Management', icon: <People />, path: '/users', adminOnly: true },
  { text: 'Agency Management', icon: <Business />, path: '/agencies', adminOnly: true },
  { text: 'Audit Logs', icon: <Security />, path: '/audit-logs', adminOnly: true },
  { text: 'Profile', icon: <Person />, path: '/profile' },
];

function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);

  const handleDrawerToggle = () => setMobileOpen(!mobileOpen);
  const handleMenuOpen = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  const handleLogout = async () => {
    handleMenuClose();
    await logout();
    navigate('/login');
  };

  const filteredNav = navItems.filter((item) => !item.adminOnly || isAdmin());

  const drawerContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Logo */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          px: 2.5,
          py: 2.5,
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <Shield
          sx={{
            fontSize: 36,
            color: '#00D4FF',
            filter: 'drop-shadow(0 0 8px rgba(0,212,255,0.4))',
          }}
        />
        <Box>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 800,
              background: 'linear-gradient(135deg, #00D4FF, #00E676)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              fontSize: '1.1rem',
              lineHeight: 1.2,
            }}
          >
            CyberAudit
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
            Report Management
          </Typography>
        </Box>
      </Box>

      {/* Nav Items */}
      <List sx={{ flex: 1, px: 1.5, py: 2 }}>
        {filteredNav.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                onClick={() => {
                  navigate(item.path);
                  if (isMobile) setMobileOpen(false);
                }}
                sx={{
                  borderRadius: 2,
                  py: 1.2,
                  px: 2,
                  mb: 0.5,
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  backgroundColor: isActive ? 'rgba(0, 212, 255, 0.08)' : 'transparent',
                  borderLeft: isActive ? '4px solid #00D4FF' : '4px solid transparent',
                  boxShadow: isActive ? 'inset 20px 0 20px -20px rgba(0,212,255,0.5)' : 'none',
                  position: 'relative',
                  overflow: 'hidden',
                  '&::before': isActive ? {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    background: 'linear-gradient(90deg, rgba(0,212,255,0.1) 0%, transparent 100%)',
                    zIndex: 0
                  } : {},
                  '&:hover': {
                    backgroundColor: isActive ? 'rgba(0, 212, 255, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                    transform: 'translateX(4px)',
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 40,
                    color: isActive ? '#00D4FF' : 'text.secondary',
                    zIndex: 1,
                    transition: 'all 0.3s ease',
                    transform: isActive ? 'scale(1.1)' : 'scale(1)',
                    filter: isActive ? 'drop-shadow(0 0 5px rgba(0,212,255,0.5))' : 'none',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  sx={{ zIndex: 1 }}
                  primaryTypographyProps={{
                    fontWeight: isActive ? 600 : 400,
                    fontSize: '0.875rem',
                    color: isActive ? '#E2E8F0' : 'text.secondary',
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      {/* User info at bottom */}
      <Box
        sx={{
          p: 2,
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
        }}
      >
        <Avatar
          sx={{
            width: 36,
            height: 36,
            background: 'linear-gradient(135deg, #00D4FF, #7C4DFF)',
            fontSize: '0.9rem',
            fontWeight: 700,
          }}
        >
          {user?.username?.charAt(0).toUpperCase() || 'U'}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="body2"
            fontWeight={600}
            noWrap
            sx={{ fontSize: '0.8rem' }}
          >
            {user?.full_name || user?.username}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ fontSize: '0.7rem' }}
          >
            {user?.roles?.join(', ')}
          </Typography>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* AppBar */}
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {isMobile && (
              <IconButton color="inherit" onClick={handleDrawerToggle} edge="start">
                <MenuIcon />
              </IconButton>
            )}
            <Typography variant="h6" noWrap sx={{ fontWeight: 600, fontSize: '1rem' }}>
              {navItems.find((n) => n.path === location.pathname)?.text || 'CyberAudit'}
            </Typography>
          </Box>

          <Box>
            <IconButton onClick={handleMenuOpen} sx={{ p: 0.5 }}>
              <Avatar
                sx={{
                  width: 34,
                  height: 34,
                  background: 'linear-gradient(135deg, #00D4FF, #7C4DFF)',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </Avatar>
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              transformOrigin={{ horizontal: 'right', vertical: 'top' }}
              anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
              PaperProps={{
                sx: { mt: 1, minWidth: 180 },
              }}
            >
              <MenuItem
                onClick={() => {
                  handleMenuClose();
                  navigate('/profile');
                }}
              >
                <ListItemIcon><Person fontSize="small" /></ListItemIcon>
                Profile
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>
                <ListItemIcon><Logout fontSize="small" sx={{ color: 'error.main' }} /></ListItemIcon>
                <Typography color="error.main">Logout</Typography>
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Sidebar Drawer */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={handleDrawerToggle}
            ModalProps={{ keepMounted: true }}
            sx={{
              '& .MuiDrawer-paper': { width: DRAWER_WIDTH },
            }}
          >
            {drawerContent}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              '& .MuiDrawer-paper': { width: DRAWER_WIDTH },
            }}
            open
          >
            {drawerContent}
          </Drawer>
        )}
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px',
          overflow: 'auto',
          height: 'calc(100vh - 64px)',
        }}
      >
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -15 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          style={{ height: '100%' }}
        >
          <Outlet />
        </motion.div>
      </Box>
    </Box>
  );
}

export default Layout;
