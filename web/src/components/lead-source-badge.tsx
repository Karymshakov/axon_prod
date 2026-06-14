import { Badge } from '@/components/ui/badge'

interface LeadSourceBadgeProps {
  source: string | null | undefined
  label?: string
  className?: string
}

export function LeadSourceBadge({ source, label: displayLabel, className }: LeadSourceBadgeProps) {
  if (!source) return null

  const s = source.trim()
  const lower = s.toLowerCase()

  // Premium, harmonious color palettes using HSL tailwind colors with dark borders
  let colorClasses = 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/50 dark:text-slate-400 dark:border-slate-800'
  let label = displayLabel || s

  if (lower === 'website' || lower === 'сайт') {
    colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:border-indigo-900/50'
    label = 'Сайт'
  } else if (lower === 'friends' || lower === 'referral' || lower === 'рекомендация' || lower === 'сарафанное радио') {
    colorClasses = 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900/50'
    label = 'Рекомендация'
  } else if (lower === 'social media' || lower === 'социальные сети' || lower === 'instagram' || lower === 'инстаграм') {
    colorClasses = 'bg-pink-50 text-pink-700 border-pink-200 dark:bg-pink-950/30 dark:text-pink-400 dark:border-pink-900/50'
    label = lower.includes('insta') ? 'Instagram' : 'Соц. сети'
  } else if (lower === 'telegram' || lower === 'телеграм' || lower === 'tg') {
    colorClasses = 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/30 dark:text-sky-400 dark:border-sky-900/50'
    label = 'Telegram'
  } else if (lower === 'whatsapp' || lower === 'ватсап' || lower === 'wa') {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/50'
    label = 'WhatsApp'
  } else if (lower === 'email campaign' || lower === 'email-кампания' || lower === 'email') {
    colorClasses = 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950/30 dark:text-cyan-400 dark:border-cyan-900/50'
    label = 'Email'
  } else if (lower === 'cold call' || lower === 'холодный звонок') {
    colorClasses = 'bg-zinc-50 text-zinc-600 border-zinc-200 dark:bg-zinc-950/30 dark:text-zinc-400 dark:border-zinc-900/50'
    label = 'Холодный звонок'
  } else if (lower === 'trade show' || lower === 'выставка') {
    colorClasses = 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-400 dark:border-slate-800'
    label = 'Выставка'
  } else if (lower === 'advertisement' || lower === 'реклама' || lower === 'ads') {
    colorClasses = 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/30 dark:text-violet-400 dark:border-violet-900/50'
    label = 'Реклама'
  } else if (lower === 'google' || lower === 'search' || lower === 'поиск') {
    colorClasses = 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-900/50'
    label = 'Google'
  } else if (lower === 'partner' || lower === 'партнёр') {
    colorClasses = 'bg-yellow-50 text-yellow-800 border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-400 dark:border-yellow-900/50'
    label = 'Партнёр'
  } else if (lower === 'repeat_guest' || lower === 'repeat guest' || lower === 'повторный гость') {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/50'
    label = 'Повторный гость'
  } else if (lower === 'booking' || lower === 'booking.com' || lower === 'букинг') {
    colorClasses = 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-900/50'
    label = 'Booking.com'
  } else if (lower === 'other' || lower === 'другое') {
    colorClasses = 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-950/20 dark:text-slate-400 dark:border-slate-900/50'
    label = 'Другое'
  }

  return (
    <Badge variant="outline" className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 border ${colorClasses} ${className}`}>
      {label}
    </Badge>
  )
}
