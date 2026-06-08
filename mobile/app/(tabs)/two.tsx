import { View } from 'react-native'

import { Separator } from '@/components/ui/separator'
import { Text } from '@/components/ui/text'

export default function TabTwoScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-background">
      <Text className="text-xl font-bold text-foreground">Tab Two</Text>
      <Separator className="my-8 w-4/5" />
      <Text className="text-muted-foreground">Edit app/(tabs)/two.tsx to change this screen</Text>
    </View>
  )
}
