package com.xwray.groupie

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView

/**
 * Мини-реализация Groupie 2.x API (com.xwray.groupie.Item / ViewHolder / GroupAdapter).
 * Официальный groupie 2.1.0 был только на jcenter (мёртв), а JitPack в этом окружении
 * отдаёт 401 — поэтому локальный шим с идентичными сигнатурами, чтобы не переписывать
 * все экраны. Поведение: плоский список, bind по позиции, notifyDataSetChanged на мутациях
 * (для учебных объёмов сообщений более чем достаточно).
 */
// ViewHolder НЕ объявляем своим классом: это RecyclerView.ViewHolder (itemView public).
// Собственный com.xwray.groupie.ViewHolder с полем itemView опасен: если в classpath
// APK оказывается настоящий groupie 2.x (package-private itemView), компилятор берёт
// наш класс, а рантайм — его, и вызов .itemView из чужого пакета даёт IllegalAccessError
// (реальный краш LatestKartinkaMessageRow.bind на Samsung). typealias стирается в байткод,
// так что оба варианта совпадают всегда.
typealias ViewHolder = RecyclerView.ViewHolder

/**
 * Защита асинхронных колбэков от переиспользования ячейки (бывш. ViewHolder.boundPosition).
 * Расширение объявлено на конкретном RecyclerView.ViewHolder, а НЕ на typealias
 * (typealias ViewHolder -> RecyclerView.ViewHolder), иначе компилятор видит два
 * объявления boundPosition для одного класса и падает с "Val cannot be reassigned".
 */
val RecyclerView.ViewHolder.boundPosition: Int
    get() = (tag as? Int) ?: RecyclerView.NO_POSITION

fun RecyclerView.ViewHolder.setBoundPosition(position: Int) {
    tag = position
}

/** Замена Kotlin Synthetics: holder["some_id"] -> findViewById(R.id.some_id). */
operator fun ViewHolder.get(name: String): android.view.View? =
    itemView.findViewById(ViewIdResolver.idOf(name))

abstract class Item<VH : ViewHolder> {
    abstract fun getLayout(): Int
    abstract fun bind(viewHolder: VH, position: Int)
    /**
     * Как в настоящем Groupie 2.x: фабричный метод возвращает базовый ViewHolder.
     * Все экраны проекта параметризованы Item<ViewHolder>, поэтому дженерик-VH здесь не нужен —
     * прежняя версия с "return RecyclerView.ViewHolder(view) as VH" не компилировалась
     * (Cannot create an instance of an abstract class: typealias ViewHolder -> RecyclerView.ViewHolder).
     */
    open fun createViewHolder(parent: ViewGroup): ViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(getLayout(), parent, false)
        return ViewHolder(view)
    }
    open val id: Long get() = hashCode().toLong()
}

class GroupAdapter<VH : ViewHolder> : RecyclerView.Adapter<ViewHolder>() {

    private val items = mutableListOf<Item<*>>()

    private var onItemClickListener: ((Item<*>, android.view.View) -> Unit)? = null
    fun setOnItemClickListener(listener: (Item<*>, android.view.View) -> Unit) {
        onItemClickListener = listener
    }

    fun add(item: Item<*>) {
        items.add(item)
        notifyItemInserted(items.size - 1)
    }

    /**
     * Дифф-обновление списка. Точечные уведомления (inserted/removed) выпускаются только
     * когда изменены ИСКЛЮЧИТЕЛЬНО хвостовые позиции — тогда старые индексы валидны для
     * notifyItemRange*. Любые другие варианты (добавление/замена в середине, перестановка)
     * безопасно уходят в notifyDataSetChanged(). Это чинит O(n^2) пересборку всего списка
     * на каждое новое сообщение в LatestMessagesActivity.
     */
    fun updateWithDiff(newItems: List<Item<*>>) {
        val old = ArrayList<Item<*>>(items)
        items.clear()
        items.addAll(newItems)

        // длина изменилась только за счёт хвоста, и префикс совпадает по id -> точечное уведомление
        val minLen = Math.min(old.size, newItems.size)
        var common = 0
        while (common < minLen && old[common].id == newItems[common].id) common++

        val tailOnlyChange =
            (newItems.size > old.size && common == old.size) ||   // добавлены элементы в конец
            (old.size > newItems.size && common == newItems.size) // удалён хвост
        if (tailOnlyChange) {
            if (newItems.size > old.size) {
                notifyItemRangeInserted(old.size, newItems.size - old.size)
            } else {
                notifyItemRangeRemoved(newItems.size, old.size - newItems.size)
            }
            return
        }
        if (old.size == newItems.size && common == old.size) return // идентично, ничего не меняем
        notifyDataSetChanged()
    }

    fun update(newItems: List<Item<*>>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun clear() {
        val size = items.size
        items.clear()
        notifyItemRangeRemoved(0, size)
    }

    override fun getItemCount(): Int = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        return items[firstNonNegative(viewType)].createViewHolder(parent)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.setBoundPosition(position)
        @Suppress("UNCHECKED_CAST")
        (items[position] as Item<ViewHolder>).bind(holder, position)
        holder.itemView.setOnClickListener {
            val idx = holder.bindingAdapterPosition
            if (idx != androidx.recyclerview.widget.RecyclerView.NO_POSITION) {
                onItemClickListener?.invoke(items[idx], holder.itemView)
            }
        }
    }

    // viewType == позиция при стабильных ID запрещаем; используем позицию как viewType
    override fun getItemViewType(position: Int): Int = position

    private fun firstNonNegative(v: Int) = if (v >= 0) v else 0
}
