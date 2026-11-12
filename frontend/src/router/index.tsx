import { Navigate, createBrowserRouter } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { Login } from '../pages/Login';
import { Pairs } from '../pages/Pairs';
import { BatchNew } from '../pages/BatchNew';
import { BatchDetail } from '../pages/BatchDetail';
import { Diffs } from '../pages/Diffs';
import { Tickets } from '../pages/Tickets';

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/pairs" replace /> },
      { path: 'pairs', element: <Pairs /> },
      { path: 'batches/new', element: <BatchNew /> },
      { path: 'batches/:batchId', element: <BatchDetail /> },
      { path: 'diffs', element: <Diffs /> },
      { path: 'tickets', element: <Tickets /> },
      { path: '*', element: <Navigate to="/pairs" replace /> },
    ],
  },
]);
