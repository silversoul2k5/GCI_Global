import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { Text } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AppConfigProvider } from './config';
import HomeScreen from './screens/HomeScreen';
import OffersScreen from './screens/OffersScreen';

const Tab = createBottomTabNavigator();

function TabIcon({ emoji }) {
  return <Text style={{ fontSize: 18 }}>{emoji}</Text>;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppConfigProvider>
        <StatusBar style="dark" />
        <NavigationContainer>
          <Tab.Navigator
            screenOptions={{
              headerShown: false,
              tabBarActiveTintColor: '#2F6FED',
              tabBarInactiveTintColor: '#9AA2B1',
              tabBarStyle: { paddingBottom: 6, paddingTop: 6, height: 58 },
              tabBarLabelStyle: { fontSize: 11.5, fontWeight: '600' },
            }}
          >
            <Tab.Screen
              name="Home"
              component={HomeScreen}
              options={{ tabBarIcon: () => <TabIcon emoji="🏠" /> }}
            />
            <Tab.Screen
              name="Offers"
              component={OffersScreen}
              options={{ tabBarIcon: () => <TabIcon emoji="🎁" /> }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </AppConfigProvider>
    </SafeAreaProvider>
  );
}
