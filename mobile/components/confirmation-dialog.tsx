import { Alert, Platform } from 'react-native'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Text } from '@/components/ui/text'

interface ConfirmationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  title?: string
  description?: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'destructive'
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  onConfirm,
  title = 'Are you sure?',
  description = 'This action cannot be undone.',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'default',
}: ConfirmationDialogProps) {
  // On native, use Alert.alert for native feel
  if (Platform.OS !== 'web') {
    if (open) {
      Alert.alert(
        title,
        description,
        [
          {
            text: cancelText,
            style: 'cancel',
            onPress: () => onOpenChange(false),
          },
          {
            text: confirmText,
            style: variant === 'destructive' ? 'destructive' : 'default',
            onPress: () => {
              onConfirm()
              onOpenChange(false)
            },
          },
        ],
        { cancelable: true, onDismiss: () => onOpenChange(false) }
      )
      // Immediately set open to false since Alert.alert is imperative
      setTimeout(() => onOpenChange(false), 0)
    }
    return null
  }

  // On web, use AlertDialog component
  // Only override colors for destructive variant - AlertDialogAction already has button base styles
  const destructiveStyles = variant === 'destructive'
    ? 'bg-destructive hover:bg-destructive/90 active:bg-destructive/90'
    : ''

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            <Text>{cancelText}</Text>
          </AlertDialogCancel>
          <AlertDialogAction
            onPress={() => {
              onConfirm()
              onOpenChange(false)
            }}
            className={destructiveStyles}
          >
            <Text className={variant === 'destructive' ? 'text-white' : ''}>
              {confirmText}
            </Text>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
