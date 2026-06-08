import { useState } from 'react'
import { format } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import type { DateRange } from 'react-day-picker'

import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

interface DateRangePickerProps {
  value?: { from?: string; to?: string }
  onChange: (range?: { from?: string; to?: string }) => void
  placeholder?: string
  disabled?: boolean
}

const parseLocalDate = (dateStr: string) => new Date(dateStr + 'T00:00:00')

const isCompleteRange = (range?: DateRange) =>
  range?.from && range?.to && range.from.getTime() !== range.to.getTime()

export function DateRangePicker({ value, onChange, placeholder = 'Pick a date range', disabled }: DateRangePickerProps) {
  const [open, setOpen] = useState(false)
  const [dateRange, setDateRange] = useState<DateRange | undefined>()

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen)
    if (isOpen) {
      const hasCompleteRange = value?.from && value?.to
      setDateRange(hasCompleteRange ? undefined :
        value?.from ? { from: parseLocalDate(value.from), to: undefined } : undefined)
    }
  }

  const handleSelect = (range: DateRange | undefined) => {
    setDateRange(range)
    if (isCompleteRange(range)) {
      onChange({ from: format(range!.from!, 'yyyy-MM-dd'), to: format(range!.to!, 'yyyy-MM-dd') })
      setOpen(false)
    }
  }

  const handleClear = () => {
    setDateRange(undefined)
    onChange(undefined)
    setOpen(false)
  }

  const displayValue = !value?.from ? placeholder :
    !value.to ? format(parseLocalDate(value.from), 'MMM d, yyyy') :
    `${format(parseLocalDate(value.from), 'MMM d, yyyy')} - ${format(parseLocalDate(value.to), 'MMM d, yyyy')}`

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className={cn('w-full justify-start text-left font-normal', !value?.from && 'text-muted-foreground')}
        >
          <CalendarIcon className="mr-2 size-4 shrink-0" />
          <span className="truncate">{displayValue}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0 max-w-[min(calc(100vw-2rem),800px)]" align="start">
        <Calendar
          mode="range"
          defaultMonth={dateRange?.from}
          selected={dateRange}
          onSelect={handleSelect}
          numberOfMonths={2}
        />
        {(dateRange || value?.from) && (
          <div className="flex justify-end border-t p-3">
            <Button variant="ghost" size="sm" onClick={handleClear}>
              Clear
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
