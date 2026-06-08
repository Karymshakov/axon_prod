import { useState } from 'react'
import { Platform, View } from 'react-native'
import DateTimePicker from '@react-native-community/datetimepicker'
import { CalendarIcon } from 'lucide-react-native'

import { Button } from '@/components/ui/button'
import { Text } from '@/components/ui/text'
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

interface DatePickerProps {
  value?: Date
  onChange: (date: Date | undefined) => void
  placeholder?: string
  minimumDate?: Date
  maximumDate?: Date
}

const months = [
  { value: '0', label: 'January' },
  { value: '1', label: 'February' },
  { value: '2', label: 'March' },
  { value: '3', label: 'April' },
  { value: '4', label: 'May' },
  { value: '5', label: 'June' },
  { value: '6', label: 'July' },
  { value: '7', label: 'August' },
  { value: '8', label: 'September' },
  { value: '9', label: 'October' },
  { value: '10', label: 'November' },
  { value: '11', label: 'December' },
]

const generateYears = () => {
  const currentYear = new Date().getFullYear()
  const years = []
  for (let i = currentYear - 100; i <= currentYear + 10; i++) {
    years.push({ value: String(i), label: String(i) })
  }
  return years
}

const generateDays = (month: number, year: number) => {
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days = []
  for (let i = 1; i <= daysInMonth; i++) {
    days.push({ value: String(i), label: String(i) })
  }
  return days
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export function DatePicker({
  value,
  onChange,
  placeholder = 'Select date',
  minimumDate,
  maximumDate,
}: DatePickerProps) {
  const [showPicker, setShowPicker] = useState(false)
  const [open, setOpen] = useState(false)

  // Temp state for web popover
  const [tempMonth, setTempMonth] = useState(value?.getMonth() ?? new Date().getMonth())
  const [tempDay, setTempDay] = useState(value?.getDate() ?? new Date().getDate())
  const [tempYear, setTempYear] = useState(value?.getFullYear() ?? new Date().getFullYear())

  // Native iOS/Android picker
  if (Platform.OS !== 'web') {
    return (
      <View>
        <Button
          variant="outline"
          onPress={() => setShowPicker(true)}
          className="w-full justify-start"
        >
          <CalendarIcon className="mr-2 size-4 text-muted-foreground" />
          <Text className={cn(!value && 'text-muted-foreground')}>
            {value ? formatDate(value) : placeholder}
          </Text>
        </Button>

        {showPicker && (
          <DateTimePicker
            value={value || new Date()}
            mode="date"
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            onChange={(event, selectedDate) => {
              setShowPicker(Platform.OS === 'ios')
              if (event.type === 'set' && selectedDate) {
                onChange(selectedDate)
              }
              if (Platform.OS === 'android') {
                setShowPicker(false)
              }
            }}
            minimumDate={minimumDate}
            maximumDate={maximumDate}
          />
        )}
      </View>
    )
  }

  // Web: Popover with Select dropdowns
  const years = generateYears()
  const days = generateDays(tempMonth, tempYear)

  return (
    <Popover
      open={open}
      onOpenChange={(isOpen) => {
        if (isOpen && value) {
          setTempMonth(value.getMonth())
          setTempDay(value.getDate())
          setTempYear(value.getFullYear())
        }
        setOpen(isOpen)
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className="w-full justify-start">
          <CalendarIcon className="mr-2 size-4 text-muted-foreground" />
          <Text className={cn(!value && 'text-muted-foreground')}>
            {value ? formatDate(value) : placeholder}
          </Text>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto">
        <View className="gap-4">
          <Text className="font-semibold">Select Date</Text>
          <View className="flex-row gap-3">
            <Select
              value={{ value: String(tempMonth), label: months[tempMonth].label }}
              onValueChange={(option) => option && setTempMonth(Number(option.value))}
            >
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Month" />
              </SelectTrigger>
              <SelectContent>
                {months.map((month) => (
                  <SelectItem key={month.value} value={month.value} label={month.label}>
                    {month.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={{ value: String(tempDay), label: String(tempDay) }}
              onValueChange={(option) => option && setTempDay(Number(option.value))}
            >
              <SelectTrigger className="w-18">
                <SelectValue placeholder="Day" />
              </SelectTrigger>
              <SelectContent>
                {days.map((day) => (
                  <SelectItem key={day.value} value={day.value} label={day.label}>
                    {day.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={{ value: String(tempYear), label: String(tempYear) }}
              onValueChange={(option) => option && setTempYear(Number(option.value))}
            >
              <SelectTrigger className="w-24">
                <SelectValue placeholder="Year" />
              </SelectTrigger>
              <SelectContent>
                {years.map((year) => (
                  <SelectItem key={year.value} value={year.value} label={year.label}>
                    {year.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </View>
          <View className="flex-row justify-end gap-2">
            <PopoverClose asChild>
              <Button variant="outline" size="sm">
                <Text>Cancel</Text>
              </Button>
            </PopoverClose>
            <PopoverClose asChild>
              <Button size="sm" onPress={() => onChange(new Date(tempYear, tempMonth, tempDay))}>
                <Text>Confirm</Text>
              </Button>
            </PopoverClose>
          </View>
        </View>
      </PopoverContent>
    </Popover>
  )
}
