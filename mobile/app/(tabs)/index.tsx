import { View } from 'react-native'
import { useQuery } from '@tanstack/react-query'

import { Card, CardContent } from '@/components/ui/card'
import { Text } from '@/components/ui/text'
import { fetchHealth } from '@/lib/api'

export default function HomeScreen() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })

  return (
    <View className="flex-1 items-center justify-center p-5 bg-background">
      <Text className="text-2xl font-bold mb-2 text-foreground">Django + React Native</Text>
      <Text className="text-base opacity-70 mb-6 text-foreground">Expo SDK 54</Text>

      <Card className="w-full">
        <CardContent className="items-center p-6">
          {isLoading && <Text className="text-muted-foreground">Loading...</Text>}
          {error && <Text className="text-destructive">Error connecting to backend</Text>}
          {data && (
            <>
              <Text className="text-green-600 font-semibold text-base">Backend connected!</Text>
              <Text className="mt-2 text-sm text-muted-foreground">{data.message}</Text>
            </>
          )}
        </CardContent>
      </Card>
    </View>
  )
}
