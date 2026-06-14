import { StatusBar } from 'expo-status-bar'
import { Platform, View } from 'react-native'

import { Separator } from '@/components/ui/separator'
import { Text } from '@/components/ui/text'

export default function ModalScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-background">
      <Text className="text-xl font-bold text-foreground">Modal</Text>
      <Separator className="my-8 w-4/5" />
      <Text className="text-muted-foreground">Edit app/modal.tsx to change this screen</Text>

      {/* Use a light status bar on iOS to account for the black space above the modal */}
      <StatusBar style={Platform.OS === 'ios' ? 'light' : 'auto'} />
    </View>
  )
}
