package com.example.fess.kotlinmassage1.views

import android.widget.ImageView
import android.widget.TextView
import com.example.fess.kotlinmassage1.R
import com.example.fess.kotlinmassage1.models.ChatMessage
import com.example.fess.kotlinmassage1.models.User
import com.example.fess.kotlinmassage1.util.ImageLoader
import com.example.fess.kotlinmassage1.util.ImageUtils
import com.google.firebase.auth.FirebaseAuth
import com.squareup.picasso.Picasso
import com.xwray.groupie.Item
// boundPosition — extension-свойство из локального шима Groupie, нужен явный импорт.
import com.xwray.groupie.boundPosition
// ViewHolder из com.xwray.groupie — это typealias на RecyclerView.ViewHolder (itemView public).
// Раньше здесь был свой класс с полем itemView, и если в classpath APK попадал настоящий
// groupie 2.x (package-private itemView), на устройстве был IllegalAccessError (краш bind()).
import com.xwray.groupie.ViewHolder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Общий контракт строк диалогов: по клику активити нужен собеседник. */
interface DialogItem {
    val chatPartnerUser: User?
}

/**
 * Строка списка диалогов (обычное текстовое сообщение).
 * Профиль собеседника подтягивается через ImageLoader.fetchUser (колбэк в main),
 * аватар — Picasso c превью-ресайзом.
 */
class LatestMessageRow(val chatMessage: ChatMessage) : Item<ViewHolder>(), DialogItem {

    /** Имя собеседника доступно по клику (см. LatestMessagesActivity). */
    override var chatPartnerUser: User? = null
        private set

    override fun bind(viewHolder: ViewHolder, position: Int) {
        
        viewHolder.itemView.findViewById<TextView>(R.id.text_textview_latest_message).text =
            chatMessage.text.take(120)

        val partnerId = chatMessage.partnerId(FirebaseAuth.getInstance().uid)
        ImageLoader.fetchUser(partnerId) { user ->
            if (user == null) return@fetchUser
            chatPartnerUser = user
            // ViewHolder мог быть переиспользован за время запроса — проверяем привязку
            if (viewHolder.boundPosition != position) return@fetchUser
            viewHolder.itemView.findViewById<TextView>(R.id.username_textview_latest_message).text = user.username
            ImageLoader.loadAvatarInto(
                user.profileImageUrl,
                viewHolder.itemView.findViewById(R.id.imageview_latest_message)
            )
        }
    }

    override fun getLayout(): Int = R.layout.latest_message_row
}

/**
 * Строка списка диалогов с картинкой. Декод base64 — в фоновом пуле (ImageLoader),
 * раньше выполнялся синхронно в bind() и фризил список на каждом бинде.
 */
class LatestKartinkaMessageRow(val chatMessage: ChatMessage) : Item<ViewHolder>(), DialogItem {

    override var chatPartnerUser: User? = null
        private set

    override fun bind(viewHolder: ViewHolder, position: Int) {
        
        val time = SimpleDateFormat("dd-MM-yyyy HH:mm:ss", Locale.getDefault())
            .format(Date(chatMessage.timestamp * 1000))
        viewHolder.itemView.findViewById<TextView>(R.id.textDate_message_time2).text = time

        val isImage = chatMessage.type == ChatMessage.TYPE_IMAGE
        val previewText = viewHolder.itemView.findViewById<TextView>(R.id.text_kartinka_textview_latest_message3)
        val image = viewHolder.itemView.findViewById<ImageView>(R.id.kartinka_imageview_latest_message)

        if (isImage) {
            previewText.text = "📷 Картинка"
            if (ImageUtils.isImagePayload(chatMessage.text)) {
                ImageLoader.loadBase64ToView(chatMessage.text, image)
            } else {
                // обратная совместимость со старыми URL из Firebase Storage
                Picasso.get().load(chatMessage.text).into(image)
            }
        } else {
            previewText.text = chatMessage.text.take(80)
        }

        val partnerId = chatMessage.partnerId(FirebaseAuth.getInstance().uid)
        ImageLoader.fetchUser(partnerId) { user ->
            if (user == null) return@fetchUser
            chatPartnerUser = user
            if (viewHolder.boundPosition != position) return@fetchUser
            viewHolder.itemView.findViewById<TextView>(R.id.username_kartinka_textview_latest_message).text = user.username
            ImageLoader.loadAvatarInto(
                user.profileImageUrl,
                viewHolder.itemView.findViewById(R.id.imageview_latest_message1)
            )
        }
    }

    override fun getLayout(): Int = R.layout.latest_image_message_row
}
