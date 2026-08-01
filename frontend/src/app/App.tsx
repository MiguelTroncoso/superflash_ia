import { AppProviders } from './providers'
import { AppRoutes } from '../routes/AppRoutes'
import { BrowserRouter } from 'react-router'

export function App(): React.JSX.Element {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppRoutes />
      </AppProviders>
    </BrowserRouter>
  )
}
